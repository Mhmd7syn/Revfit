// lib/Screens/live_pose_screen.dart
import 'dart:async';
import 'dart:convert';
import 'dart:ui';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:gym2/colors/colors.dart';
import 'package:gym2/services/auth_service.dart';
import 'package:gym2/services/pose_service.dart';
import 'package:gym2/services/recommendation_service.dart';
import 'skeleton_painter.dart';

class LivePoseScreen extends StatefulWidget {
  const LivePoseScreen({super.key});

  @override
  State<LivePoseScreen> createState() => _LivePoseScreenState();
}

class _LivePoseScreenState extends State<LivePoseScreen>
    with TickerProviderStateMixin {
  // ── Camera ────────────────────────────────────────────────────────────
  CameraController? _camCtrl;
  List<CameraDescription> _cameras = [];
  int _cameraIndex = 0;
  bool _isFrontCamera = false;

  // ── Session ───────────────────────────────────────────────────────────
  String? _sessionId;
  final _recommendationService = RecommendationService();

  // ── Exercise selection ────────────────────────────────────────────────
  List<String> _exercises = [];
  String? _selectedExercise;
  bool _isLoadingExercises = true;

  // ── WebSocket / Live stream ───────────────────────────────────────────
  WebSocketChannel? _wsChannel;
  StreamSubscription? _wsSub;
  bool _isStreaming = false;
  Timer? _frameTimer;
  static const int _targetFps = 10;

  // ── Real-time data from server ────────────────────────────────────────
  bool _isGoodForm = true;
  List<String> _feedbackMessages = [];
  int _repCount = 0;
  double _formScore = 100.0;
  List<List<double>> _landmarks = [];

  // ── Session timer ─────────────────────────────────────────────────────
  DateTime? _sessionStart;
  Timer? _clockTimer;
  Duration _elapsed = Duration.zero;

  // ── Overlay toggle ────────────────────────────────────────────────────
  bool _showSkeleton = true;

  // ── Animations ────────────────────────────────────────────────────────
  late AnimationController _pulseCtrl;
  late AnimationController _scoreCtrl;
  late Animation<double> _pulseAnim;

  // ── Error ─────────────────────────────────────────────────────────────
  String? _errorMsg;

  // ── Lifecycle ─────────────────────────────────────────────────────────
  @override
  void initState() {
    super.initState();
    _pulseCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    )..repeat(reverse: true);
    _pulseAnim = Tween<double>(begin: 0.6, end: 1.0).animate(
      CurvedAnimation(parent: _pulseCtrl, curve: Curves.easeInOut),
    );

    _scoreCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    );

    _initCamera();
    _loadExercises();
  }

  @override
  void dispose() {
    _stopStreaming();
    _clockTimer?.cancel();
    _frameTimer?.cancel();
    _camCtrl?.dispose();
    _pulseCtrl.dispose();
    _scoreCtrl.dispose();
    _wsSub?.cancel();
    _wsChannel?.sink.close();
    super.dispose();
  }

  // ── Camera setup ──────────────────────────────────────────────────────
  Future<void> _initCamera() async {
    try {
      _cameras = await availableCameras();
      if (_cameras.isEmpty) {
        setState(() => _errorMsg = 'No cameras available on this device.');
        return;
      }
      // Default to rear camera
      _cameraIndex = _cameras.indexWhere(
        (c) => c.lensDirection == CameraLensDirection.back,
      );
      if (_cameraIndex < 0) _cameraIndex = 0;
      await _startCamera(_cameraIndex);
    } catch (e) {
      setState(() => _errorMsg = 'Camera init failed: $e');
    }
  }

  Future<void> _startCamera(int index) async {
    _camCtrl?.dispose();
    final cam = _cameras[index];
    _isFrontCamera = cam.lensDirection == CameraLensDirection.front;
    final ctrl = CameraController(
      cam,
      ResolutionPreset.medium,
      enableAudio: false,
      imageFormatGroup: ImageFormatGroup.jpeg,
    );
    try {
      await ctrl.initialize();
      if (mounted) setState(() => _camCtrl = ctrl);
    } catch (e) {
      setState(() => _errorMsg = 'Camera start failed: $e');
    }
  }

  void _switchCamera() {
    if (_cameras.length < 2) return;
    _cameraIndex = (_cameraIndex + 1) % _cameras.length;
    _startCamera(_cameraIndex);
  }

  // ── Exercise loading ──────────────────────────────────────────────────
  Future<void> _loadExercises() async {
    try {
      final list = await PoseService.getSupportedExercises();
      if (mounted) {
        setState(() {
          _exercises = list;
          _isLoadingExercises = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMsg = 'Could not load exercises. Is the server running?';
          _isLoadingExercises = false;
        });
      }
    }
  }

  // ── Session management ────────────────────────────────────────────────
  Future<void> _ensureSession() async {
    if (_sessionId != null) return;
    final user = AuthService().currentUser;
    if (user == null) throw Exception('User not logged in');

    final payload = {
      'age': user.age,
      'height_cm': user.height,
      'weight_kg': user.weight,
      'sex': user.gender.toLowerCase(),
      'goal_type': user.goalType.toLowerCase(),
      'fitness_level': 'beginner',
      'activity_level': 'light',
      'workout_location': 'both',
      'available_equipment': <String>[],
      'diet_type': user.defaultDietType,
      'allergies': <String>[],
      'intolerances': <String>[],
    };
    _sessionId = await _recommendationService.createSession(payload);
  }

  // ── Streaming control ─────────────────────────────────────────────────
  Future<void> _startStreaming() async {
    if (_selectedExercise == null || _camCtrl == null) return;

    setState(() {
      _errorMsg = null;
      _isGoodForm = true;
      _feedbackMessages = [];
      _repCount = 0;
      _formScore = 100.0;
      _landmarks = [];
    });

    try {
      await _ensureSession();

      // Connect WebSocket
      _wsChannel = PoseService.connectLive(
        sessionId: _sessionId!,
        exerciseName: _selectedExercise!,
      );

      // Listen for server responses
      _wsSub = _wsChannel!.stream.listen(
        (message) {
          if (!mounted) return;
          try {
            final data = json.decode(message as String) as Map<String, dynamic>;
            setState(() {
              _isGoodForm = data['is_good_form'] as bool? ?? true;
              _feedbackMessages = List<String>.from(
                data['feedback_messages'] as List? ?? [],
              );
              _repCount = data['rep_count'] as int? ?? 0;
              _formScore = (data['form_score'] as num?)?.toDouble() ?? 100.0;
              final rawLandmarks = data['landmarks'] as List? ?? [];
              _landmarks = rawLandmarks
                  .map<List<double>>(
                    (lm) => List<double>.from(
                      (lm as List).map((v) => (v as num).toDouble()),
                    ),
                  )
                  .toList();
            });
          } catch (_) {}
        },
        onError: (e) {
          if (mounted) {
            setState(() => _errorMsg = 'Connection lost: $e');
            _stopStreaming();
          }
        },
        onDone: () {
          if (mounted && _isStreaming) {
            _stopStreaming();
          }
        },
      );

      // Start sending frames
      _isStreaming = true;
      _sessionStart = DateTime.now();
      _elapsed = Duration.zero;

      _clockTimer = Timer.periodic(const Duration(seconds: 1), (_) {
        if (mounted && _sessionStart != null) {
          setState(() {
            _elapsed = DateTime.now().difference(_sessionStart!);
          });
        }
      });

      // Capture and send frames at target FPS
      _frameTimer = Timer.periodic(
        Duration(milliseconds: (1000 / _targetFps).round()),
        (_) => _captureAndSendFrame(),
      );

      setState(() {});
    } catch (e) {
      setState(() => _errorMsg = 'Failed to start: $e');
    }
  }

  Future<void> _captureAndSendFrame() async {
    if (!_isStreaming || _camCtrl == null || !_camCtrl!.value.isInitialized) {
      return;
    }
    try {
      final xFile = await _camCtrl!.takePicture();
      final bytes = await xFile.readAsBytes();
      _wsChannel?.sink.add(bytes);
    } catch (_) {
      // Silently skip dropped frames
    }
  }

  void _stopStreaming() {
    _frameTimer?.cancel();
    _frameTimer = null;
    _clockTimer?.cancel();
    _clockTimer = null;
    _wsSub?.cancel();
    _wsSub = null;

    if (_isStreaming) {
      _wsChannel?.sink.close();
      _wsChannel = null;
      _isStreaming = false;

      // Show summary dialog
      if (mounted && _repCount > 0) {
        _showSummaryDialog();
      }
    }

    if (mounted) setState(() {});
  }

  // ── Summary dialog ────────────────────────────────────────────────────
  void _showSummaryDialog() {
    final scoreColor = _formScore >= 80
        ? AppColors.successColor
        : _formScore >= 50
            ? AppColors.warningColor
            : AppColors.errorColor;

    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (ctx) => Container(
        padding: const EdgeInsets.all(24),
        decoration: const BoxDecoration(
          color: AppColors.cardBg,
          borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Handle bar
            Container(
              width: 40,
              height: 4,
              margin: const EdgeInsets.only(bottom: 20),
              decoration: BoxDecoration(
                color: AppColors.textMuted.withOpacity(0.3),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            // Title
            const Text(
              'Session Complete 🎯',
              style: TextStyle(
                color: AppColors.textPrimary,
                fontSize: 22,
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 20),
            // Score circle
            SizedBox(
              width: 100,
              height: 100,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  SizedBox(
                    width: 100,
                    height: 100,
                    child: CircularProgressIndicator(
                      value: _formScore / 100,
                      strokeWidth: 8,
                      color: scoreColor,
                      backgroundColor: scoreColor.withOpacity(0.15),
                    ),
                  ),
                  Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        '${_formScore.round()}',
                        style: TextStyle(
                          color: scoreColor,
                          fontSize: 28,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      Text(
                        'Score',
                        style: TextStyle(
                          color: scoreColor.withOpacity(0.7),
                          fontSize: 11,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),
            // Stats row
            Row(
              children: [
                _summaryStatChip(
                  'Reps',
                  '$_repCount',
                  AppColors.primary,
                ),
                const SizedBox(width: 12),
                _summaryStatChip(
                  'Duration',
                  _formatDuration(_elapsed),
                  AppColors.secondary,
                ),
                const SizedBox(width: 12),
                _summaryStatChip(
                  'Exercise',
                  _titleCase(_selectedExercise ?? ''),
                  AppColors.accent3,
                ),
              ],
            ),
            const SizedBox(height: 20),
            // Feedback
            if (_feedbackMessages.isNotEmpty) ...[
              Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  'Key Feedback',
                  style: TextStyle(
                    color: AppColors.textPrimary,
                    fontWeight: FontWeight.w700,
                    fontSize: 14,
                  ),
                ),
              ),
              const SizedBox(height: 8),
              ...(_feedbackMessages.toSet().take(5).map(
                    (msg) => Padding(
                      padding: const EdgeInsets.only(bottom: 4),
                      child: Row(
                        children: [
                          const Icon(Icons.warning_amber_rounded,
                              color: AppColors.warningColor, size: 14),
                          const SizedBox(width: 6),
                          Expanded(
                            child: Text(
                              msg,
                              style: const TextStyle(
                                color: AppColors.textMuted,
                                fontSize: 12,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  )),
            ],
            const SizedBox(height: 24),
            // Close button
            SizedBox(
              width: double.infinity,
              height: 52,
              child: DecoratedBox(
                decoration: BoxDecoration(
                  gradient: AppColors.primaryGradient,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: MaterialButton(
                  onPressed: () => Navigator.pop(ctx),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: const Text(
                    'Done',
                    style: TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.w700,
                      fontSize: 16,
                    ),
                  ),
                ),
              ),
            ),
            SizedBox(height: MediaQuery.of(ctx).padding.bottom + 8),
          ],
        ),
      ),
    );
  }

  Widget _summaryStatChip(String label, String value, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: BoxDecoration(
          color: color.withOpacity(0.08),
          borderRadius: BorderRadius.circular(14),
        ),
        child: Column(
          children: [
            Text(
              value,
              style: TextStyle(
                color: color,
                fontWeight: FontWeight.w800,
                fontSize: 16,
              ),
              textAlign: TextAlign.center,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 2),
            Text(
              label,
              style: const TextStyle(color: AppColors.textMuted, fontSize: 10),
            ),
          ],
        ),
      ),
    );
  }

  // ── Helpers ───────────────────────────────────────────────────────────
  String _formatDuration(Duration d) {
    final m = d.inMinutes.remainder(60).toString().padLeft(2, '0');
    final s = d.inSeconds.remainder(60).toString().padLeft(2, '0');
    return '$m:$s';
  }

  String _titleCase(String s) {
    if (s.isEmpty) return s;
    return s
        .split(' ')
        .map((w) => w.isEmpty ? '' : '${w[0].toUpperCase()}${w.substring(1)}')
        .join(' ');
  }

  // ── Build ─────────────────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.darkBg,
      body: Stack(
        fit: StackFit.expand,
        children: [
          // Camera preview or placeholder
          _buildCameraPreview(),

          // Skeleton overlay
          if (_showSkeleton && _landmarks.isNotEmpty && _isStreaming)
            Positioned.fill(
              child: CustomPaint(
                painter: SkeletonPainter(
                  landmarks: _landmarks,
                  isGoodForm: _isGoodForm,
                  isFrontCamera: _isFrontCamera,
                ),
              ),
            ),

          // Top HUD
          _buildTopHud(),

          // Feedback bar (bottom)
          if (_isStreaming) _buildFeedbackBar(),

          // Bottom controls
          _buildBottomControls(),

          // Exercise selector (shown when not streaming)
          if (!_isStreaming) _buildExerciseSelector(),

          // Error overlay
          if (_errorMsg != null) _buildErrorOverlay(),
        ],
      ),
    );
  }

  // ── Camera preview ────────────────────────────────────────────────────
  Widget _buildCameraPreview() {
    if (_camCtrl == null || !_camCtrl!.value.isInitialized) {
      return Container(
        color: AppColors.darkBg,
        child: const Center(
          child: CircularProgressIndicator(color: AppColors.primary),
        ),
      );
    }

    return ClipRRect(
      borderRadius: BorderRadius.circular(0),
      child: Transform.scale(
        scale: 1.0,
        child: Center(
          child: CameraPreview(_camCtrl!),
        ),
      ),
    );
  }

  // ── Top HUD (score, reps, timer, back) ────────────────────────────────
  Widget _buildTopHud() {
    return Positioned(
      top: 0,
      left: 0,
      right: 0,
      child: Container(
        padding: EdgeInsets.fromLTRB(
          16,
          MediaQuery.of(context).padding.top + 8,
          16,
          12,
        ),
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              Colors.black.withOpacity(0.7),
              Colors.black.withOpacity(0.0),
            ],
          ),
        ),
        child: Row(
          children: [
            // Back button
            _hudButton(
              icon: Icons.arrow_back_ios_new_rounded,
              onTap: () {
                _stopStreaming();
                Navigator.pop(context);
              },
            ),
            const Spacer(),

            if (_isStreaming) ...[
              // Recording indicator
              AnimatedBuilder(
                animation: _pulseAnim,
                builder: (_, __) => Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: Colors.red.withOpacity(0.15 * _pulseAnim.value),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(
                      color: Colors.red.withOpacity(0.5 * _pulseAnim.value),
                    ),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        width: 8,
                        height: 8,
                        decoration: BoxDecoration(
                          color: Colors.red.withOpacity(_pulseAnim.value),
                          shape: BoxShape.circle,
                        ),
                      ),
                      const SizedBox(width: 6),
                      Text(
                        _formatDuration(_elapsed),
                        style: TextStyle(
                          color: Colors.white.withOpacity(0.9),
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          fontFeatures: const [FontFeature.tabularFigures()],
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(width: 12),

              // Form score badge
              _buildScoreBadge(),

              const SizedBox(width: 12),

              // Rep count
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                decoration: BoxDecoration(
                  color: AppColors.primary.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: AppColors.primary.withOpacity(0.4),
                  ),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.replay_rounded,
                        color: AppColors.primary, size: 16),
                    const SizedBox(width: 4),
                    Text(
                      '$_repCount',
                      style: const TextStyle(
                        color: AppColors.primary,
                        fontSize: 16,
                        fontWeight: FontWeight.w800,
                        fontFeatures: [FontFeature.tabularFigures()],
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildScoreBadge() {
    final scoreColor = _formScore >= 80
        ? AppColors.successColor
        : _formScore >= 50
            ? AppColors.warningColor
            : AppColors.errorColor;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: scoreColor.withOpacity(0.15),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: scoreColor.withOpacity(0.4)),
      ),
      child: Text(
        '${_formScore.round()}%',
        style: TextStyle(
          color: scoreColor,
          fontSize: 14,
          fontWeight: FontWeight.w800,
        ),
      ),
    );
  }

  Widget _hudButton({required IconData icon, required VoidCallback onTap}) {
    return GestureDetector(
      onTap: onTap,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(14),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
          child: Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.1),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: Colors.white.withOpacity(0.15)),
            ),
            child: Icon(icon, color: Colors.white, size: 18),
          ),
        ),
      ),
    );
  }

  // ── Feedback bar ──────────────────────────────────────────────────────
  Widget _buildFeedbackBar() {
    if (_feedbackMessages.isEmpty && _isGoodForm) {
      return Positioned(
        bottom: 120,
        left: 20,
        right: 20,
        child: Center(
          child: ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: BackdropFilter(
              filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                decoration: BoxDecoration(
                  color: AppColors.successColor.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(
                    color: AppColors.successColor.withOpacity(0.3),
                  ),
                ),
                child: const Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.check_circle_rounded,
                        color: AppColors.successColor, size: 18),
                    SizedBox(width: 8),
                    Text(
                      'Good Form ✓',
                      style: TextStyle(
                        color: AppColors.successColor,
                        fontWeight: FontWeight.w700,
                        fontSize: 14,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      );
    }

    return Positioned(
      bottom: 120,
      left: 16,
      right: 16,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
          child: Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppColors.errorColor.withOpacity(0.12),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: AppColors.errorColor.withOpacity(0.3),
              ),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: _feedbackMessages.take(3).map((msg) {
                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 2),
                  child: Row(
                    children: [
                      const Icon(Icons.warning_amber_rounded,
                          color: AppColors.warningColor, size: 14),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          msg,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 12,
                            fontWeight: FontWeight.w500,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                );
              }).toList(),
            ),
          ),
        ),
      ),
    );
  }

  // ── Bottom controls ───────────────────────────────────────────────────
  Widget _buildBottomControls() {
    return Positioned(
      bottom: 0,
      left: 0,
      right: 0,
      child: ClipRRect(
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 20, sigmaY: 20),
          child: Container(
            padding: EdgeInsets.fromLTRB(
              24,
              16,
              24,
              MediaQuery.of(context).padding.bottom + 16,
            ),
            decoration: BoxDecoration(
              color: Colors.black.withOpacity(0.4),
              border: Border(
                top: BorderSide(
                  color: Colors.white.withOpacity(0.08),
                ),
              ),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                // Skeleton toggle
                _controlButton(
                  icon: _showSkeleton
                      ? Icons.visibility_rounded
                      : Icons.visibility_off_rounded,
                  label: 'Skeleton',
                  isActive: _showSkeleton,
                  onTap: () => setState(() => _showSkeleton = !_showSkeleton),
                ),

                // Start / Stop button
                GestureDetector(
                  onTap: () {
                    if (_isStreaming) {
                      _stopStreaming();
                    } else if (_selectedExercise != null) {
                      _startStreaming();
                    }
                  },
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 200),
                    width: 72,
                    height: 72,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: _isStreaming
                          ? const LinearGradient(
                              colors: [Color(0xFFE53935), Color(0xFFB71C1C)],
                            )
                          : (_selectedExercise != null
                              ? AppColors.primaryGradient
                              : const LinearGradient(
                                  colors: [
                                    Color(0xFF333333),
                                    Color(0xFF222222)
                                  ],
                                )),
                      boxShadow: [
                        if (_selectedExercise != null || _isStreaming)
                          BoxShadow(
                            color: (_isStreaming
                                    ? Colors.red
                                    : AppColors.primary)
                                .withOpacity(0.4),
                            blurRadius: 20,
                            spreadRadius: 2,
                          ),
                      ],
                    ),
                    child: Icon(
                      _isStreaming
                          ? Icons.stop_rounded
                          : Icons.play_arrow_rounded,
                      color: Colors.white,
                      size: 36,
                    ),
                  ),
                ),

                // Camera flip
                _controlButton(
                  icon: Icons.flip_camera_ios_rounded,
                  label: 'Flip',
                  isActive: false,
                  onTap: _cameras.length >= 2 ? _switchCamera : null,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _controlButton({
    required IconData icon,
    required String label,
    required bool isActive,
    VoidCallback? onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: isActive
                  ? AppColors.primary.withOpacity(0.15)
                  : Colors.white.withOpacity(0.08),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(
                color: isActive
                    ? AppColors.primary.withOpacity(0.4)
                    : Colors.white.withOpacity(0.1),
              ),
            ),
            child: Icon(
              icon,
              color: isActive
                  ? AppColors.primary
                  : (onTap != null
                      ? Colors.white.withOpacity(0.7)
                      : Colors.white.withOpacity(0.3)),
              size: 22,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            label,
            style: TextStyle(
              color: Colors.white.withOpacity(0.5),
              fontSize: 10,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  // ── Exercise selector overlay ─────────────────────────────────────────
  Widget _buildExerciseSelector() {
    return Positioned(
      bottom: 130,
      left: 24,
      right: 24,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 16, sigmaY: 16),
          child: Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: AppColors.cardBg.withOpacity(0.85),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: Colors.white.withOpacity(0.1)),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Row(
                  children: [
                    Icon(Icons.fitness_center_rounded,
                        color: AppColors.primary, size: 18),
                    SizedBox(width: 8),
                    Text(
                      'Select Exercise',
                      style: TextStyle(
                        color: AppColors.textPrimary,
                        fontWeight: FontWeight.w700,
                        fontSize: 15,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                _isLoadingExercises
                    ? const Center(
                        child: Padding(
                          padding: EdgeInsets.all(16),
                          child: CircularProgressIndicator(
                            color: AppColors.primary,
                            strokeWidth: 2,
                          ),
                        ),
                      )
                    : DropdownButtonFormField<String>(
                        value: _exercises.contains(_selectedExercise)
                            ? _selectedExercise
                            : null,
                        dropdownColor: AppColors.cardBg,
                        style: const TextStyle(color: AppColors.textPrimary),
                        decoration: InputDecoration(
                          filled: true,
                          fillColor: AppColors.darkBg,
                          hintText: 'Choose an exercise…',
                          hintStyle:
                              const TextStyle(color: AppColors.textMuted),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(14),
                            borderSide: BorderSide.none,
                          ),
                          contentPadding: const EdgeInsets.symmetric(
                            horizontal: 16,
                            vertical: 14,
                          ),
                        ),
                        items: _exercises
                            .map(
                              (e) => DropdownMenuItem(
                                value: e,
                                child: Text(
                                  _titleCase(e),
                                  style: const TextStyle(fontSize: 14),
                                ),
                              ),
                            )
                            .toList(),
                        onChanged: (v) =>
                            setState(() => _selectedExercise = v),
                      ),
                if (_selectedExercise != null) ...[
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Icon(Icons.info_outline_rounded,
                          color: AppColors.textMuted.withOpacity(0.5),
                          size: 14),
                      const SizedBox(width: 6),
                      const Text(
                        'Position yourself in frame, then tap ▶ to start',
                        style: TextStyle(
                          color: AppColors.textMuted,
                          fontSize: 11,
                        ),
                      ),
                    ],
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }

  // ── Error overlay ─────────────────────────────────────────────────────
  Widget _buildErrorOverlay() {
    return Positioned(
      top: MediaQuery.of(context).padding.top + 60,
      left: 24,
      right: 24,
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppColors.errorColor.withOpacity(0.15),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppColors.errorColor.withOpacity(0.3)),
        ),
        child: Row(
          children: [
            const Icon(Icons.error_outline_rounded,
                color: AppColors.errorColor, size: 18),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                _errorMsg!,
                style: const TextStyle(
                  color: AppColors.errorColor,
                  fontSize: 12,
                ),
              ),
            ),
            GestureDetector(
              onTap: () => setState(() => _errorMsg = null),
              child: const Icon(Icons.close_rounded,
                  color: AppColors.errorColor, size: 18),
            ),
          ],
        ),
      ),
    );
  }
}
