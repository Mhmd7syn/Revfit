// lib/Screens/live_pose_screen.dart
//
// ╔══════════════════════════════════════════════════════════════════════╗
// ║  ⚠️  TESTING MODE                                                   ║
// ║                                                                      ║
// ║  Backend reads the video from the server filesystem and streams      ║
// ║  annotated frames here — no camera capture needed.                  ║
// ║                                                                      ║
// ║  Set _kTestVideoServerPath to the absolute path on the PC/server.   ║
// ╚══════════════════════════════════════════════════════════════════════╝

import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:gym2/colors/colors.dart';
import 'package:gym2/services/auth_service.dart';
import 'package:gym2/services/pose_service.dart';
import 'package:gym2/services/recommendation_service.dart';

/// ── TESTING MODE CONFIG ────────────────────────────────────────────────────
/// Server-side (PC) absolute path to the test video.
/// The backend reads it directly with cv2.VideoCapture and loops it.
const String _kTestVideoServerPath =
    '/home/kero/Downloads/lateral raise_1.mp4';
/// ──────────────────────────────────────────────────────────────────────────

class LivePoseScreen extends StatefulWidget {
  const LivePoseScreen({super.key});

  @override
  State<LivePoseScreen> createState() => _LivePoseScreenState();
}

class _LivePoseScreenState extends State<LivePoseScreen>
    with TickerProviderStateMixin {
  // ── Session ───────────────────────────────────────────────────────────
  String? _sessionId;
  final _recommendationService = RecommendationService();

  // ── Exercise selection ────────────────────────────────────────────────
  List<String> _exercises = [];
  String? _selectedExercise;
  bool _isLoadingExercises = true;

  // ── WebSocket ─────────────────────────────────────────────────────────
  WebSocketChannel? _wsChannel;
  StreamSubscription? _wsSub;
  bool _isStreaming = false;

  // ── Annotated frame received from backend ─────────────────────────────
  /// Latest annotated JPEG (skeleton drawn by OpenCV on the backend).
  /// Null until the first frame arrives.
  Uint8List? _currentFrame;

  // ── Real-time HUD data ────────────────────────────────────────────────
  bool _isGoodForm = true;
  List<String> _feedbackMessages = [];
  int _repCount = 0;
  double _formScore = 100.0;

  // ── Session timer ─────────────────────────────────────────────────────
  DateTime? _sessionStart;
  Timer? _clockTimer;
  Duration _elapsed = Duration.zero;

  // ── Animations ────────────────────────────────────────────────────────
  late AnimationController _pulseCtrl;
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
    _loadExercises();
  }

  @override
  void dispose() {
    _stopStreaming(showSummary: false);
    _clockTimer?.cancel();
    _pulseCtrl.dispose();
    super.dispose();
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

  /// Start the live session.
  /// In test mode the backend reads _kTestVideoServerPath and pushes frames.
  Future<void> _startStreaming() async {
    if (_selectedExercise == null) return;

    setState(() {
      _errorMsg = null;
      _isGoodForm = true;
      _feedbackMessages = [];
      _repCount = 0;
      _formScore = 100.0;
      _currentFrame = null;
    });

    try {
      await _ensureSession();

      // Connect — pass the server-side video path so the backend reads it
      _wsChannel = PoseService.connectLive(
        sessionId: _sessionId!,
        exerciseName: _selectedExercise!,
        testVideoServerPath: _kTestVideoServerPath,
      );

      // Listen for messages — same protocol as form checker:
      //   text  → JSON {"type":"frame", ...}  → HUD update
      //   binary → annotated JPEG             → displayed as _currentFrame
      _wsSub = _wsChannel!.stream.listen(
        (message) {
          if (!mounted) return;
          if (message is String) {
            _handleTextMessage(message);
          } else if (message is List<int>) {
            setState(() {
              _currentFrame = Uint8List.fromList(message);
            });
          }
        },
        onError: (e) {
          if (mounted) {
            setState(() => _errorMsg = 'Connection lost: $e');
            _stopStreaming(showSummary: false);
          }
        },
        onDone: () {
          if (mounted && _isStreaming) {
            _stopStreaming(showSummary: true);
          }
        },
      );

      // Start session clock
      _sessionStart = DateTime.now();
      _elapsed = Duration.zero;
      _clockTimer = Timer.periodic(const Duration(seconds: 1), (_) {
        if (mounted && _sessionStart != null) {
          setState(() => _elapsed = DateTime.now().difference(_sessionStart!));
        }
      });

      setState(() => _isStreaming = true);
    } catch (e) {
      setState(() => _errorMsg = 'Failed to start: $e');
    }
  }

  /// Handle JSON text messages — identical to form checker's _handleTextMessage.
  void _handleTextMessage(String raw) {
    try {
      final data = json.decode(raw) as Map<String, dynamic>;
      final type = data['type'] as String? ?? '';
      if (type == 'frame') {
        setState(() {
          _isGoodForm = data['is_good_form'] as bool? ?? true;
          _feedbackMessages =
              List<String>.from(data['feedback'] as List? ?? []);
          _repCount = data['rep_count'] as int? ?? _repCount;
          _formScore =
              (data['form_score'] as num?)?.toDouble() ?? _formScore;
        });
      } else if (type == 'error') {
        setState(() => _errorMsg = data['message'] as String? ?? 'Error');
      }
    } catch (_) {}
  }

  void _stopStreaming({bool showSummary = true}) {
    _clockTimer?.cancel();
    _clockTimer = null;
    _wsSub?.cancel();
    _wsSub = null;
    _wsChannel?.sink.close();
    _wsChannel = null;

    if (_isStreaming) {
      _isStreaming = false;
      if (mounted && showSummary && _repCount > 0) {
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
            // drag handle
            Container(
              width: 40,
              height: 4,
              margin: const EdgeInsets.only(bottom: 20),
              decoration: BoxDecoration(
                color: AppColors.textMuted.withOpacity(0.3),
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const Text(
              'Session Complete 🎯',
              style: TextStyle(
                color: AppColors.textPrimary,
                fontSize: 22,
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 20),
            // score ring
            SizedBox(
              width: 100,
              height: 100,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  CircularProgressIndicator(
                    value: _formScore / 100,
                    strokeWidth: 8,
                    color: scoreColor,
                    backgroundColor: scoreColor.withOpacity(0.15),
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
                      Text('Score',
                          style: TextStyle(
                              color: scoreColor.withOpacity(0.7),
                              fontSize: 11)),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),
            // stat chips
            Row(
              children: [
                _statChip('Reps', '$_repCount', AppColors.primary),
                const SizedBox(width: 12),
                _statChip(
                    'Duration', _formatDuration(_elapsed), AppColors.secondary),
                const SizedBox(width: 12),
                _statChip('Exercise', _titleCase(_selectedExercise ?? ''),
                    AppColors.accent3),
              ],
            ),
            const SizedBox(height: 20),
            if (_feedbackMessages.isNotEmpty) ...[
              Align(
                alignment: Alignment.centerLeft,
                child: Text('Key Feedback',
                    style: const TextStyle(
                      color: AppColors.textPrimary,
                      fontWeight: FontWeight.w700,
                      fontSize: 14,
                    )),
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
                            child: Text(msg,
                                style: const TextStyle(
                                    color: AppColors.textMuted, fontSize: 12)),
                          ),
                        ],
                      ),
                    ),
                  )),
            ],
            const SizedBox(height: 24),
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
                      borderRadius: BorderRadius.circular(14)),
                  child: const Text('Done',
                      style: TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w700,
                          fontSize: 16)),
                ),
              ),
            ),
            SizedBox(height: MediaQuery.of(ctx).padding.bottom + 8),
          ],
        ),
      ),
    );
  }

  Widget _statChip(String label, String value, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: BoxDecoration(
          color: color.withOpacity(0.08),
          borderRadius: BorderRadius.circular(14),
        ),
        child: Column(
          children: [
            Text(value,
                style: TextStyle(
                    color: color,
                    fontWeight: FontWeight.w800,
                    fontSize: 16),
                textAlign: TextAlign.center,
                maxLines: 1,
                overflow: TextOverflow.ellipsis),
            const SizedBox(height: 2),
            Text(label,
                style: const TextStyle(
                    color: AppColors.textMuted, fontSize: 10)),
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

  String _titleCase(String s) => s
      .split(' ')
      .map((w) => w.isEmpty
          ? ''
          : '${w[0].toUpperCase()}${w.substring(1)}')
      .join(' ');

  // ── Build ─────────────────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.darkBg,
      body: Stack(
        fit: StackFit.expand,
        children: [
          // ① Main content — annotated frames from backend fill the screen
          _buildFrameView(),

          // ② Top HUD (back button, timer, score, reps)
          _buildTopHud(),

          // ③ Feedback pill (bottom-center, above controls)
          if (_isStreaming) _buildFeedbackPill(),

          // ④ Bottom bar (exercise selector when idle, stop button when streaming)
          _buildBottomControls(),

          // ⑤ Testing mode badge
          _buildTestingBadge(),

          // ⑥ Error overlay
          if (_errorMsg != null) _buildErrorOverlay(),
        ],
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────
  // ① Frame view
  // ─────────────────────────────────────────────────────────────────────

  Widget _buildFrameView() {
    if (_currentFrame != null) {
      // Annotated JPEG from backend — fill screen like a camera feed
      return SizedBox.expand(
        child: Image.memory(
          _currentFrame!,
          fit: BoxFit.cover,
          gaplessPlayback: true,
        ),
      );
    }

    if (_isStreaming) {
      // Waiting for first frame — show a dark camera-like loading state
      return Container(
        color: Colors.black,
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const SizedBox(
                width: 32,
                height: 32,
                child: CircularProgressIndicator(
                    color: AppColors.primary, strokeWidth: 2),
              ),
              const SizedBox(height: 14),
              Text(
                'Loading pose engine…',
                style: TextStyle(
                    color: Colors.white.withOpacity(0.45), fontSize: 13),
              ),
            ],
          ),
        ),
      );
    }

    // Idle — camera viewfinder look: black with corner brackets
    return Container(
      color: Colors.black,
      child: CustomPaint(
        painter: _ViewfinderPainter(),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────
  // ② Top HUD
  // ─────────────────────────────────────────────────────────────────────

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
              Colors.black.withOpacity(0.65),
              Colors.transparent,
            ],
          ),
        ),
        child: Row(
          children: [
            // Back button
            _glassButton(
              icon: Icons.arrow_back_ios_new_rounded,
              onTap: () {
                _stopStreaming(showSummary: false);
                Navigator.pop(context);
              },
            ),
            const Spacer(),

            if (_isStreaming) ...[
              // Recording dot + elapsed timer
              AnimatedBuilder(
                animation: _pulseAnim,
                builder: (_, __) => _glassPill(
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

              const SizedBox(width: 8),

              // Form score
              _buildScorePill(),

              const SizedBox(width: 8),

              // Rep count
              _glassPill(
                color: AppColors.primary.withOpacity(0.15),
                borderColor: AppColors.primary.withOpacity(0.4),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.replay_rounded,
                        color: AppColors.primary, size: 15),
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

  Widget _buildScorePill() {
    final c = _formScore >= 80
        ? AppColors.successColor
        : _formScore >= 50
            ? AppColors.warningColor
            : AppColors.errorColor;
    return _glassPill(
      color: c.withOpacity(0.15),
      borderColor: c.withOpacity(0.4),
      child: Text(
        '${_formScore.round()}%',
        style: TextStyle(
            color: c, fontSize: 14, fontWeight: FontWeight.w800),
      ),
    );
  }

  Widget _glassPill({
    required Widget child,
    Color? color,
    Color? borderColor,
  }) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(20),
      child: BackdropFilter(
        filter: ui.ImageFilter.blur(sigmaX: 10, sigmaY: 10),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
          decoration: BoxDecoration(
            color: color ?? Colors.white.withOpacity(0.1),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
                color: borderColor ?? Colors.white.withOpacity(0.15)),
          ),
          child: child,
        ),
      ),
    );
  }

  Widget _glassButton(
      {required IconData icon, required VoidCallback onTap}) {
    return GestureDetector(
      onTap: onTap,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(14),
        child: BackdropFilter(
          filter: ui.ImageFilter.blur(sigmaX: 10, sigmaY: 10),
          child: Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.1),
              borderRadius: BorderRadius.circular(14),
              border:
                  Border.all(color: Colors.white.withOpacity(0.15)),
            ),
            child: Icon(icon, color: Colors.white, size: 18),
          ),
        ),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────
  // ③ Feedback pill
  // ─────────────────────────────────────────────────────────────────────

  Widget _buildFeedbackPill() {
    final bool waiting = _currentFrame == null;
    final bool goodForm = _isGoodForm && _feedbackMessages.isEmpty;

    // Position the pill above the bottom bar
    const double bottomOffset = 100;

    if (waiting || goodForm) {
      return Positioned(
        bottom: bottomOffset,
        left: 0,
        right: 0,
        child: Center(
          child: ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: BackdropFilter(
              filter: ui.ImageFilter.blur(sigmaX: 12, sigmaY: 12),
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                decoration: BoxDecoration(
                  color: waiting
                      ? Colors.white.withOpacity(0.08)
                      : AppColors.successColor.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(
                    color: waiting
                        ? Colors.white.withOpacity(0.15)
                        : AppColors.successColor.withOpacity(0.3),
                  ),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      waiting
                          ? Icons.hourglass_top_rounded
                          : Icons.check_circle_rounded,
                      color: waiting
                          ? Colors.white.withOpacity(0.6)
                          : AppColors.successColor,
                      size: 16,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      waiting ? 'Detecting pose…' : 'Good Form ✓',
                      style: TextStyle(
                        color: waiting
                            ? Colors.white.withOpacity(0.7)
                            : AppColors.successColor,
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

    // Feedback messages
    return Positioned(
      bottom: bottomOffset,
      left: 16,
      right: 16,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: BackdropFilter(
          filter: ui.ImageFilter.blur(sigmaX: 12, sigmaY: 12),
          child: Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppColors.errorColor.withOpacity(0.12),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                  color: AppColors.errorColor.withOpacity(0.3)),
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
                        child: Text(msg,
                            style: const TextStyle(
                                color: Colors.white,
                                fontSize: 12,
                                fontWeight: FontWeight.w500),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis),
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

  // ─────────────────────────────────────────────────────────────────────
  // ④ Bottom controls
  // ─────────────────────────────────────────────────────────────────────

  Widget _buildBottomControls() {
    final bool canStart =
        _selectedExercise != null && !_isLoadingExercises;

    return Positioned(
      bottom: 0,
      left: 0,
      right: 0,
      child: ClipRRect(
        child: BackdropFilter(
          filter: ui.ImageFilter.blur(sigmaX: 20, sigmaY: 20),
          child: Container(
            padding: EdgeInsets.fromLTRB(
              24,
              12,
              24,
              MediaQuery.of(context).padding.bottom + 16,
            ),
            decoration: BoxDecoration(
              color: Colors.black.withOpacity(0.45),
              border: Border(
                top: BorderSide(
                    color: Colors.white.withOpacity(0.08)),
              ),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // ── Exercise picker row (visible when not streaming) ────
                if (!_isStreaming) ..._buildExercisePicker(),

                const SizedBox(height: 8),

                // ── Buttons row ────────────────────────────────────────
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                  children: [
                    // Left icon (info placeholder)
                    _controlIcon(
                        icon: Icons.info_outline_rounded,
                        label: 'Info',
                        enabled: false),

                    // Start / Stop
                    GestureDetector(
                      onTap: () {
                        if (_isStreaming) {
                          _stopStreaming();
                        } else if (canStart) {
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
                              ? const LinearGradient(colors: [
                                  Color(0xFFE53935),
                                  Color(0xFFB71C1C)
                                ])
                              : (canStart
                                  ? AppColors.primaryGradient
                                  : const LinearGradient(colors: [
                                      Color(0xFF333333),
                                      Color(0xFF222222)
                                    ])),
                          boxShadow: [
                            if (canStart || _isStreaming)
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

                    // Right icon (flip — disabled in test mode)
                    _controlIcon(
                        icon: Icons.flip_camera_ios_rounded,
                        label: 'Flip',
                        enabled: false),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  /// Compact exercise picker — replaces the old floating selector card.
  /// Shown inline inside the bottom bar when not streaming.
  List<Widget> _buildExercisePicker() {
    if (_isLoadingExercises) {
      return [
        const SizedBox(
          height: 36,
          child: Center(
            child: SizedBox(
              width: 20,
              height: 20,
              child: CircularProgressIndicator(
                  color: AppColors.primary, strokeWidth: 2),
            ),
          ),
        ),
      ];
    }

    return [
      ClipRRect(
        borderRadius: BorderRadius.circular(12),
        child: BackdropFilter(
          filter: ui.ImageFilter.blur(sigmaX: 8, sigmaY: 8),
          child: Container(
            padding:
                const EdgeInsets.symmetric(horizontal: 14, vertical: 2),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.07),
              borderRadius: BorderRadius.circular(12),
              border:
                  Border.all(color: Colors.white.withOpacity(0.12)),
            ),
            child: DropdownButtonHideUnderline(
              child: DropdownButton<String>(
                value: _exercises.contains(_selectedExercise)
                    ? _selectedExercise
                    : null,
                isExpanded: true,
                dropdownColor: const Color(0xFF1A1A2E),
                iconEnabledColor: AppColors.primary,
                style: const TextStyle(
                    color: Colors.white,
                    fontSize: 14,
                    fontWeight: FontWeight.w500),
                hint: Row(
                  children: [
                    Icon(Icons.fitness_center_rounded,
                        color: Colors.white.withOpacity(0.4), size: 16),
                    const SizedBox(width: 8),
                    Text('Choose exercise…',
                        style: TextStyle(
                            color: Colors.white.withOpacity(0.4),
                            fontSize: 13)),
                  ],
                ),
                items: _exercises
                    .map((e) => DropdownMenuItem(
                        value: e,
                        child: Text(_titleCase(e))))
                    .toList(),
                onChanged: (v) =>
                    setState(() => _selectedExercise = v),
              ),
            ),
          ),
        ),
      ),
    ];
  }

  Widget _controlIcon(
      {required IconData icon,
      required String label,
      required bool enabled}) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 48,
          height: 48,
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.08),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: Colors.white.withOpacity(0.1)),
          ),
          child: Icon(icon,
              color: Colors.white.withOpacity(enabled ? 0.7 : 0.25),
              size: 22),
        ),
        const SizedBox(height: 4),
        Text(label,
            style: TextStyle(
                color: Colors.white.withOpacity(0.4),
                fontSize: 10,
                fontWeight: FontWeight.w500)),
      ],
    );
  }

  // ─────────────────────────────────────────────────────────────────────
  // ⑥ Testing mode badge
  // ─────────────────────────────────────────────────────────────────────

  Widget _buildTestingBadge() {
    return Positioned(
      top: MediaQuery.of(context).padding.top + 56,
      left: 0,
      right: 0,
      child: Center(
        child: Container(
          padding:
              const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
          decoration: BoxDecoration(
            color: Colors.orange.withOpacity(0.85),
            borderRadius: BorderRadius.circular(20),
          ),
          child: const Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.science_rounded,
                  color: Colors.white, size: 12),
              SizedBox(width: 4),
              Text(
                'TEST MODE — Backend Video',
                style: TextStyle(
                    color: Colors.white,
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 0.5),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ─────────────────────────────────────────────────────────────────────
  // ⑦ Error overlay
  // ─────────────────────────────────────────────────────────────────────

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
          border: Border.all(
              color: AppColors.errorColor.withOpacity(0.3)),
        ),
        child: Row(
          children: [
            const Icon(Icons.error_outline_rounded,
                color: AppColors.errorColor, size: 18),
            const SizedBox(width: 10),
            Expanded(
              child: Text(_errorMsg!,
                  style: const TextStyle(
                      color: AppColors.errorColor, fontSize: 12)),
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

// ── Camera viewfinder painter ─────────────────────────────────────────────────
/// Draws the four corner bracket marks typical of a camera viewfinder.
class _ViewfinderPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    const double arm = 28.0;    // length of each bracket arm
    const double stroke = 2.5;
    const double padding = 52.0; // inset from screen edge

    final paint = Paint()
      ..color = Colors.white.withOpacity(0.25)
      ..strokeWidth = stroke
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    // Centre guide cross (very faint)
    final crossPaint = Paint()
      ..color = Colors.white.withOpacity(0.08)
      ..strokeWidth = 1.0
      ..style = PaintingStyle.stroke;

    final cx = size.width / 2;
    final cy = size.height / 2;
    const crossLen = 16.0;
    canvas.drawLine(
        Offset(cx - crossLen, cy), Offset(cx + crossLen, cy), crossPaint);
    canvas.drawLine(
        Offset(cx, cy - crossLen), Offset(cx, cy + crossLen), crossPaint);

    // Helper: draw one corner bracket
    void corner(double x, double y, double dx, double dy) {
      canvas.drawLine(Offset(x, y), Offset(x + dx * arm, y), paint);
      canvas.drawLine(Offset(x, y), Offset(x, y + dy * arm), paint);
    }

    // Top-left
    corner(padding, padding, 1, 1);
    // Top-right
    corner(size.width - padding, padding, -1, 1);
    // Bottom-left
    corner(padding, size.height - padding, 1, -1);
    // Bottom-right
    corner(size.width - padding, size.height - padding, -1, -1);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
