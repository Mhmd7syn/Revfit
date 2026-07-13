// lib/Screens/pose_analysis_screen.dart
import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'package:video_player/video_player.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:gym2/colors/colors.dart';
import 'package:gym2/services/auth_service.dart';
import 'package:gym2/services/pose_service.dart';
import 'package:gym2/services/recommendation_service.dart';
import 'package:gym2/services/tts_service.dart';

class PoseAnalysisScreen extends StatefulWidget {
  const PoseAnalysisScreen({super.key});

  @override
  State<PoseAnalysisScreen> createState() => _PoseAnalysisScreenState();
}

/// Visual phases of the screen.
enum _ScreenPhase { upload, streaming, result }

class _PoseAnalysisScreenState extends State<PoseAnalysisScreen>
    with SingleTickerProviderStateMixin {
  // ── state ─────────────────────────────────────────────────────────────
  String? _sessionId;
  List<String> _exercises = [];
  String? _selectedExercise;
  String? _selectedFilePath;
  String? _selectedFileName;
  Uint8List? _selectedFileBytes;

  bool _isLoadingExercises = true;
  bool _isAnalyzing = false;
  Map<String, dynamic>? _result;
  String? _errorMsg;

  // ── Phase 1 classifier state ──────────────────────────────────────────
  bool _isClassifying = false;
  String? _classifiedExercise;
  double? _classificationConfidence;
  bool _showManualOverride = false;
  String? _classifyError;

  /// Confidence threshold below which we prompt manual override.
  static const double _confidenceThreshold = 0.70;

  VideoPlayerController? _videoController;

  final _recommendationService = RecommendationService();

  late AnimationController _pulseController;

  // ── Streaming state ───────────────────────────────────────────────────
  _ScreenPhase _phase = _ScreenPhase.upload;
  WebSocketChannel? _wsChannel;
  StreamSubscription? _wsSub;
  Uint8List? _currentFrame;       // Latest annotated JPEG from server
  int _streamIndex = 0;           // Current frame index
  int _streamTotal = 1;           // Total frames to process
  bool _streamIsGoodForm = true;
  List<String> _streamFeedback = [];
  int _streamRepCount = 0;
  double _streamFormScore = 100.0;
  bool _isUploading = false;

  // ── lifecycle ─────────────────────────────────────────────────────────
  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat(reverse: true);
    _loadExercises();
  }

  @override
  void dispose() {
    _pulseController.dispose();
    _videoController?.dispose();
    _wsSub?.cancel();
    _wsChannel?.sink.close();
    TtsService.instance.stop();
    super.dispose();
  }

  // ── helpers ───────────────────────────────────────────────────────────
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

  Future<void> _pickVideo() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.video,
      allowMultiple: false,
    );
    if (result != null && result.files.isNotEmpty) {
      final file = result.files.first;
      setState(() {
        _selectedFilePath = kIsWeb ? null : file.path;
        _selectedFileName = file.name;
        _selectedFileBytes = file.bytes;
        _result = null;
        _errorMsg = null;
        // Reset classification state on new video pick
        _classifiedExercise = null;
        _classificationConfidence = null;
        _showManualOverride = false;
        _classifyError = null;
      });

      // Automatically classify the video after picking
      _classifyVideo();
    }
  }

  Future<void> _classifyVideo() async {
    setState(() {
      _isClassifying = true;
      _classifyError = null;
    });

    try {
      await _ensureSession();
      final res = await PoseService.classifyExercise(
        sessionId: _sessionId!,
        videoFilePath: _selectedFilePath,
        videoBytes: _selectedFileBytes,
        videoFileName: _selectedFileName,
      );

      if (mounted) {
        final predicted = res['predicted_exercise'] as String;
        final confidence = (res['confidence'] as num).toDouble();

        setState(() {
          _classifiedExercise = predicted;
          _classificationConfidence = confidence;
          _isClassifying = false;

          if (confidence >= _confidenceThreshold) {
            // High confidence → auto-populate exercise
            _selectedExercise = predicted;
            _showManualOverride = false;
          } else {
            // Low confidence → show warning and expose dropdown
            _selectedExercise = predicted;
            _showManualOverride = true;
          }
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isClassifying = false;
          _classifyError = 'Auto-detect failed. Please select manually.';
          _showManualOverride = true;
        });
      }
    }
  }

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

  // ── Streaming analysis flow ───────────────────────────────────────────

  Future<void> _runStreamingAnalysis() async {
    final hasFile = _selectedFilePath != null || _selectedFileBytes != null;
    if (_selectedExercise == null || !hasFile) return;

    setState(() {
      _isAnalyzing = true;
      _isUploading = true;
      _errorMsg = null;
      _result = null;
      _currentFrame = null;
      _streamIndex = 0;
      _streamTotal = 1;
      _streamIsGoodForm = true;
      _streamFeedback = [];
      _streamRepCount = 0;
      _streamFormScore = 100.0;
    });

    try {
      await _ensureSession();

      // Step 1: Upload video
      final videoId = await PoseService.uploadVideo(
        sessionId: _sessionId!,
        videoFilePath: _selectedFilePath,
        videoBytes: _selectedFileBytes,
        videoFileName: _selectedFileName,
      );

      if (!mounted) return;
      setState(() {
        _isUploading = false;
        _phase = _ScreenPhase.streaming;
      });

      // Step 2: Connect WebSocket
      _wsChannel = PoseService.connectStreamAnalyze(
        sessionId: _sessionId!,
        exerciseName: _selectedExercise!,
        videoId: videoId,
      );

      // Initialize TTS
      TtsService.instance.resetCooldowns();
      await TtsService.instance.init();

      // Step 3: Listen to the stream
      _wsSub = _wsChannel!.stream.listen(
        (message) {
          if (!mounted) return;

          if (message is String) {
            // JSON text message
            _handleTextMessage(message);
          } else if (message is List<int>) {
            // Binary JPEG frame
            setState(() {
              _currentFrame = Uint8List.fromList(message);
            });
          }
        },
        onError: (e) {
          if (mounted) {
            setState(() {
              _errorMsg = 'Connection lost: $e';
              _isAnalyzing = false;
              _phase = _ScreenPhase.upload;
            });
          }
        },
        onDone: () {
          if (mounted && _phase == _ScreenPhase.streaming && _result == null) {
            // Unexpected close without completion
            setState(() {
              _isAnalyzing = false;
              _phase = _ScreenPhase.upload;
              _errorMsg = 'Connection closed unexpectedly.';
            });
          }
        },
      );
    } catch (e) {
      if (mounted) {
        setState(() {
          _isAnalyzing = false;
          _isUploading = false;
          _phase = _ScreenPhase.upload;
          _errorMsg = e.toString();
        });
      }
    }
  }

  void _handleTextMessage(String raw) {
    try {
      final data = json.decode(raw) as Map<String, dynamic>;
      final type = data['type'] as String? ?? '';

      switch (type) {
        case 'frame':
          setState(() {
            _streamIndex = data['index'] as int? ?? _streamIndex;
            _streamTotal = data['total'] as int? ?? _streamTotal;
            _streamIsGoodForm = data['is_good_form'] as bool? ?? true;
            _streamFeedback = List<String>.from(data['feedback'] as List? ?? []);
            _streamRepCount = data['rep_count'] as int? ?? _streamRepCount;
            _streamFormScore =
                (data['form_score'] as num?)?.toDouble() ?? _streamFormScore;
          });

        case 'form_correction':
          final msg = data['message'] as String? ?? '';
          if (msg.isNotEmpty) {
            TtsService.instance.speak(msg);
          }

        case 'complete':
          final result = data['result'] as Map<String, dynamic>? ?? {};
          _wsSub?.cancel();
          _wsChannel?.sink.close();

          if (mounted) {
            setState(() {
              _result = result;
              _isAnalyzing = false;
              _phase = _ScreenPhase.result;
            });

            TtsService.instance.stop();

            final videoUrl = result['video_url'] as String?;
            if (videoUrl != null) {
              _initCorrectionVideo(videoUrl);
            }
          }

        case 'error':
          setState(() {
            _errorMsg = data['message'] as String? ?? 'Unknown error';
            _isAnalyzing = false;
            _phase = _ScreenPhase.upload;
          });
      }
    } catch (_) {}
  }

  void _cancelStreaming() {
    _wsSub?.cancel();
    _wsChannel?.sink.close();
    TtsService.instance.stop();
    setState(() {
      _isAnalyzing = false;
      _phase = _ScreenPhase.upload;
      _currentFrame = null;
    });
  }

  Future<void> _initCorrectionVideo(String relativeUrl) async {
    _videoController?.dispose();
    _videoController = null;
    final fullUrl = PoseService.correctionVideoUrl(relativeUrl);
    final controller = VideoPlayerController.networkUrl(Uri.parse(fullUrl));
    try {
      await controller.initialize();
      if (mounted) {
        setState(() => _videoController = controller);
      }
    } catch (e) {
      // Video codec may not be supported in this browser
      if (mounted) {
        setState(() {
          _videoController = null;
        });
      }
      debugPrint('Video init failed: $e — download link: $fullUrl');
    }
  }

  void _resetToUpload() {
    _videoController?.dispose();
    _videoController = null;
    setState(() {
      _result = null;
      _errorMsg = null;
      _currentFrame = null;
      _phase = _ScreenPhase.upload;
    });
  }

  String _titleCase(String s) =>
      s.split(' ').map((w) => '${w[0].toUpperCase()}${w.substring(1)}').join(' ');

  // ── build ─────────────────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        width: double.infinity,
        height: double.infinity,
        decoration: const BoxDecoration(gradient: AppColors.heroGradient),
        child: SafeArea(
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 600),
              child: switch (_phase) {
                _ScreenPhase.upload => _buildUploadPhase(),
                _ScreenPhase.streaming => _buildStreamingPhase(),
                _ScreenPhase.result => _buildResultPhase(),
              },
            ),
          ),
        ),
      ),
    );
  }

  // =====================================================================
  // PHASE 1: Upload
  // =====================================================================
  Widget _buildUploadPhase() {
    return CustomScrollView(
      physics: const BouncingScrollPhysics(),
      slivers: [
        SliverToBoxAdapter(child: _buildAppBar()),
        SliverToBoxAdapter(child: _buildVideoUpload()),
        SliverToBoxAdapter(child: _buildExerciseSelector()),
        SliverToBoxAdapter(child: _buildAnalyzeButton()),
        if (_errorMsg != null) SliverToBoxAdapter(child: _buildError()),
        const SliverToBoxAdapter(child: SizedBox(height: 40)),
      ],
    );
  }

  // =====================================================================
  // PHASE 2: Streaming — live frame player with HUD
  // =====================================================================
  Widget _buildStreamingPhase() {
    final progress = _streamTotal > 0 ? _streamIndex / _streamTotal : 0.0;
    final scoreColor = _streamFormScore >= 80
        ? AppColors.successColor
        : _streamFormScore >= 50
            ? AppColors.warningColor
            : AppColors.errorColor;

    return Column(
      children: [
        // Top bar with back/cancel
        Padding(
          padding: const EdgeInsets.fromLTRB(8, 8, 16, 0),
          child: Row(
            children: [
              IconButton(
                icon: const Icon(Icons.close_rounded,
                    color: AppColors.textPrimary, size: 22),
                onPressed: _cancelStreaming,
              ),
              const Expanded(
                child: Text(
                  'Analyzing…',
                  style: TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              // Uploading indicator
              if (_isUploading)
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: AppColors.primary.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: const Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      SizedBox(
                        width: 14,
                        height: 14,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, color: AppColors.primary),
                      ),
                      SizedBox(width: 8),
                      Text('Uploading…',
                          style: TextStyle(
                              color: AppColors.primary, fontSize: 12)),
                    ],
                  ),
                ),
            ],
          ),
        ),

        const SizedBox(height: 8),

        // HUD stats row
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Row(
            children: [
              _streamHudChip(
                icon: Icons.replay_rounded,
                label: '$_streamRepCount reps',
                color: AppColors.primary,
              ),
              const SizedBox(width: 8),
              _streamHudChip(
                icon: Icons.speed_rounded,
                label: '${_streamFormScore.round()}%',
                color: scoreColor,
              ),
              const SizedBox(width: 8),
              _streamHudChip(
                icon: _streamIsGoodForm
                    ? Icons.check_circle_outline_rounded
                    : Icons.warning_amber_rounded,
                label: _streamIsGoodForm ? 'Good Form' : 'Fix Form',
                color: _streamIsGoodForm
                    ? AppColors.successColor
                    : AppColors.errorColor,
              ),
            ],
          ),
        ),

        const SizedBox(height: 12),

        // Live frame display
        Expanded(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(20),
              child: Container(
                width: double.infinity,
                decoration: BoxDecoration(
                  color: AppColors.darkBg,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: _streamIsGoodForm
                        ? AppColors.successColor.withOpacity(0.3)
                        : AppColors.errorColor.withOpacity(0.3),
                    width: 2,
                  ),
                ),
                child: _currentFrame != null
                    ? Image.memory(
                        _currentFrame!,
                        fit: BoxFit.contain,
                        gaplessPlayback: true, // Prevents flicker
                      )
                    : const Center(
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            CircularProgressIndicator(
                                color: AppColors.primary),
                            SizedBox(height: 16),
                            Text(
                              'Processing first frame…',
                              style: TextStyle(
                                  color: AppColors.textMuted, fontSize: 13),
                            ),
                          ],
                        ),
                      ),
              ),
            ),
          ),
        ),

        const SizedBox(height: 12),

        // Progress bar
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Column(
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Frame $_streamIndex / $_streamTotal',
                    style: const TextStyle(
                        color: AppColors.textMuted, fontSize: 12),
                  ),
                  Text(
                    '${(progress * 100).round()}%',
                    style: const TextStyle(
                      color: AppColors.primary,
                      fontSize: 12,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 6),
              ClipRRect(
                borderRadius: BorderRadius.circular(6),
                child: LinearProgressIndicator(
                  value: progress.clamp(0.0, 1.0),
                  minHeight: 6,
                  backgroundColor: AppColors.darkBg,
                  valueColor:
                      AlwaysStoppedAnimation<Color>(AppColors.primary),
                ),
              ),
            ],
          ),
        ),

        const SizedBox(height: 8),

        // Feedback messages (scrollable)
        if (_streamFeedback.isNotEmpty)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: AppColors.errorColor.withOpacity(0.08),
                borderRadius: BorderRadius.circular(14),
                border: Border.all(
                    color: AppColors.errorColor.withOpacity(0.2)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: _streamFeedback
                    .take(3)
                    .map((msg) => Padding(
                          padding: const EdgeInsets.only(bottom: 4),
                          child: Row(
                            children: [
                              const Icon(Icons.volume_up_rounded,
                                  color: AppColors.errorColor, size: 14),
                              const SizedBox(width: 6),
                              Expanded(
                                child: Text(
                                  msg,
                                  style: const TextStyle(
                                      color: AppColors.errorColor,
                                      fontSize: 12),
                                ),
                              ),
                            ],
                          ),
                        ))
                    .toList(),
              ),
            ),
          ),

        const SizedBox(height: 8),
      ],
    );
  }

  Widget _streamHudChip({
    required IconData icon,
    required String label,
    required Color color,
  }) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 8),
        decoration: BoxDecoration(
          color: color.withOpacity(0.1),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: color.withOpacity(0.25)),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: color, size: 16),
            const SizedBox(width: 4),
            Flexible(
              child: Text(
                label,
                style: TextStyle(
                  color: color,
                  fontSize: 12,
                  fontWeight: FontWeight.w700,
                ),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
      ),
    );
  }

  // =====================================================================
  // PHASE 3: Result (score card + correction video)
  // =====================================================================
  Widget _buildResultPhase() {
    return CustomScrollView(
      physics: const BouncingScrollPhysics(),
      slivers: [
        SliverToBoxAdapter(child: _buildResultAppBar()),
        SliverToBoxAdapter(child: _buildResultCard()),
        if (_result != null && _result!['video_url'] != null)
          SliverToBoxAdapter(child: _buildCorrectionVideoSection()),
        SliverToBoxAdapter(child: _buildNewAnalysisButton()),
        const SliverToBoxAdapter(child: SizedBox(height: 40)),
      ],
    );
  }

  Widget _buildResultAppBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(8, 8, 24, 0),
      child: Row(
        children: [
          IconButton(
            icon: const Icon(Icons.arrow_back_ios_new_rounded,
                color: AppColors.textPrimary, size: 20),
            onPressed: _resetToUpload,
          ),
          const Expanded(
            child: Text(
              'Analysis Complete',
              style: TextStyle(
                color: AppColors.textPrimary,
                fontSize: 20,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: AppColors.successColor.withOpacity(0.15),
              borderRadius: BorderRadius.circular(14),
            ),
            child: const Icon(Icons.check_circle_rounded,
                color: AppColors.successColor, size: 22),
          ),
        ],
      ),
    );
  }

  Widget _buildNewAnalysisButton() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 20, 24, 0),
      child: SizedBox(
        width: double.infinity,
        height: 52,
        child: OutlinedButton.icon(
          onPressed: _resetToUpload,
          icon: const Icon(Icons.replay_rounded, size: 18),
          label: const Text('Analyze Another Video'),
          style: OutlinedButton.styleFrom(
            foregroundColor: AppColors.primary,
            side: BorderSide(color: AppColors.primary.withOpacity(0.4)),
            shape:
                RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          ),
        ),
      ),
    );
  }

  // ── widgets ───────────────────────────────────────────────────────────
  Widget _buildAppBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(8, 8, 24, 0),
      child: Row(
        children: [
          IconButton(
            icon: const Icon(Icons.arrow_back_ios_new_rounded,
                color: AppColors.textPrimary, size: 20),
            onPressed: () => Navigator.pop(context),
          ),
          const Expanded(
            child: Text(
              'Form Checker',
              style: TextStyle(
                color: AppColors.textPrimary,
                fontSize: 20,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: AppColors.accent3.withOpacity(0.15),
              borderRadius: BorderRadius.circular(14),
            ),
            child: const Icon(Icons.sports_gymnastics_rounded,
                color: AppColors.accent3, size: 22),
          ),
        ],
      ),
    );
  }

  /// Exercise selector — now shows auto-detected result first, with manual
  /// override available.
  Widget _buildExerciseSelector() {
    final hasFile = _selectedFilePath != null || _selectedFileBytes != null;

    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 16, 24, 0),
      child: _section(
        title: 'Exercise',
        icon: Icons.fitness_center_rounded,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Classifying spinner ──
            if (_isClassifying)
              _buildClassifyingIndicator(),

            // ── Classification result chip ──
            if (!_isClassifying && _classifiedExercise != null)
              _buildClassificationResult(),

            // ── Classification error ──
            if (_classifyError != null && !_isClassifying)
              _buildClassifyError(),

            // ── Manual override dropdown ──
            if (_showManualOverride || _classifiedExercise == null) ...[
              if (_classifiedExercise != null || _classifyError != null)
                const SizedBox(height: 12),
              _buildExerciseDropdown(),
            ],

            // ── Prompt to pick video first ──
            if (!hasFile && _classifiedExercise == null && !_isClassifying)
              const Padding(
                padding: EdgeInsets.only(top: 8),
                child: Text(
                  'Upload a video to auto-detect the exercise',
                  style: TextStyle(color: AppColors.textDisabled, fontSize: 12),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildClassifyingIndicator() {
    return AnimatedBuilder(
      animation: _pulseController,
      builder: (context, child) {
        final opacity = 0.4 + (_pulseController.value * 0.6);
        return Opacity(
          opacity: opacity,
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 16),
            decoration: BoxDecoration(
              color: AppColors.primary.withOpacity(0.08),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: AppColors.primary.withOpacity(0.2)),
            ),
            child: Row(
              children: [
                SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: AppColors.primary.withOpacity(0.7),
                  ),
                ),
                const SizedBox(width: 12),
                const Text(
                  'Detecting exercise…',
                  style: TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildClassificationResult() {
    final confidence = _classificationConfidence ?? 0.0;
    final confidencePercent = (confidence * 100).round();
    final isHigh = confidence >= 0.80;
    final isMedium = confidence >= 0.50 && confidence < 0.80;

    final badgeColor = isHigh
        ? AppColors.successColor
        : isMedium
            ? AppColors.warningColor
            : AppColors.errorColor;

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: badgeColor.withOpacity(0.06),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: badgeColor.withOpacity(0.25)),
      ),
      child: Row(
        children: [
          // Confidence badge
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
            decoration: BoxDecoration(
              color: badgeColor.withOpacity(0.15),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              '$confidencePercent%',
              style: TextStyle(
                color: badgeColor,
                fontWeight: FontWeight.w800,
                fontSize: 13,
              ),
            ),
          ),
          const SizedBox(width: 12),
          // Exercise name
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _titleCase(_classifiedExercise!),
                  style: const TextStyle(
                    color: AppColors.textPrimary,
                    fontWeight: FontWeight.w700,
                    fontSize: 15,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  confidence >= _confidenceThreshold
                      ? 'Auto-detected exercise'
                      : 'Low confidence — please confirm',
                  style: TextStyle(
                    color: confidence >= _confidenceThreshold
                        ? AppColors.textMuted
                        : AppColors.warningColor,
                    fontSize: 11,
                  ),
                ),
              ],
            ),
          ),
          // Change button
          GestureDetector(
            onTap: () => setState(() => _showManualOverride = !_showManualOverride),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: AppColors.darkBg,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: const Color(0xFF2E2E3E)),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    _showManualOverride
                        ? Icons.check_rounded
                        : Icons.edit_rounded,
                    color: AppColors.textMuted,
                    size: 14,
                  ),
                  const SizedBox(width: 4),
                  Text(
                    _showManualOverride ? 'Done' : 'Change',
                    style: const TextStyle(
                      color: AppColors.textMuted,
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildClassifyError() {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.warningColor.withOpacity(0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.warningColor.withOpacity(0.2)),
      ),
      child: Row(
        children: [
          const Icon(Icons.info_outline_rounded,
              color: AppColors.warningColor, size: 16),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              _classifyError!,
              style: const TextStyle(
                  color: AppColors.warningColor, fontSize: 12),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildExerciseDropdown() {
    return _isLoadingExercises
        ? const Center(
            child: Padding(
              padding: EdgeInsets.all(16),
              child: CircularProgressIndicator(color: AppColors.primary),
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
              hintText: 'Select exercise…',
              hintStyle: const TextStyle(color: AppColors.textMuted),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(14),
                borderSide: BorderSide.none,
              ),
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            ),
            items: _exercises
                .map((e) => DropdownMenuItem(
                      value: e,
                      child: Text(
                        _titleCase(e),
                        style: const TextStyle(fontSize: 14),
                      ),
                    ))
                .toList(),
            onChanged: (v) => setState(() {
              _selectedExercise = v;
              // If manually changed, clear auto-classify visual state
              if (v != _classifiedExercise) {
                _showManualOverride = true;
              }
            }),
          );
  }

  Widget _buildVideoUpload() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 24, 24, 0),
      child: _section(
        title: 'Video',
        icon: Icons.videocam_rounded,
        child: GestureDetector(
          onTap: _pickVideo,
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 28),
            decoration: BoxDecoration(
              color: AppColors.darkBg,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(
                color: (_selectedFilePath != null || _selectedFileBytes != null)
                    ? AppColors.primary.withOpacity(0.5)
                    : const Color(0xFF2E2E3E),
              ),
            ),
            child: Center(
              child: Column(
                children: [
                  Icon(
                    (_selectedFilePath != null || _selectedFileBytes != null)
                        ? Icons.check_circle_rounded
                        : Icons.cloud_upload_rounded,
                    color: (_selectedFilePath != null || _selectedFileBytes != null)
                        ? AppColors.successColor
                        : AppColors.textMuted,
                    size: 36,
                  ),
                  const SizedBox(height: 10),
                  Text(
                    _selectedFileName ?? 'Tap to select a video file',
                    style: TextStyle(
                      color: (_selectedFilePath != null || _selectedFileBytes != null)
                          ? AppColors.textPrimary
                          : AppColors.textMuted,
                      fontSize: 14,
                    ),
                  ),
                  if (_selectedFilePath == null && _selectedFileBytes == null)
                    const Padding(
                      padding: EdgeInsets.only(top: 4),
                      child: Text(
                        'MP4, AVI, MOV supported',
                        style: TextStyle(
                            color: AppColors.textDisabled, fontSize: 11),
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

  Widget _buildAnalyzeButton() {
    final hasFile = _selectedFilePath != null || _selectedFileBytes != null;
    final ready = _selectedExercise != null && hasFile;
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 20, 24, 0),
      child: SizedBox(
        width: double.infinity,
        height: 56,
        child: DecoratedBox(
          decoration: BoxDecoration(
            gradient: ready && !_isAnalyzing
                ? AppColors.primaryGradient
                : const LinearGradient(
                    colors: [Color(0xFF333333), Color(0xFF222222)]),
            borderRadius: BorderRadius.circular(16),
            boxShadow: ready && !_isAnalyzing
                ? [
                    BoxShadow(
                      color: AppColors.primary.withOpacity(0.35),
                      blurRadius: 16,
                      offset: const Offset(0, 6),
                    )
                  ]
                : null,
          ),
          child: MaterialButton(
            onPressed: ready && !_isAnalyzing ? _runStreamingAnalysis : null,
            shape:
                RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            child: _isAnalyzing
                ? const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(
                        strokeWidth: 2.5, color: Colors.white),
                  )
                : Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.stream_rounded,
                          color: Colors.white, size: 20),
                      const SizedBox(width: 8),
                      const Text(
                        'Stream Analysis',
                        style: TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w700,
                          fontSize: 16,
                          letterSpacing: 0.5,
                        ),
                      ),
                    ],
                  ),
          ),
        ),
      ),
    );
  }

  Widget _buildError() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 16, 24, 0),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppColors.errorColor.withOpacity(0.1),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: AppColors.errorColor.withOpacity(0.3)),
        ),
        child: Row(
          children: [
            const Icon(Icons.error_outline_rounded,
                color: AppColors.errorColor, size: 20),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                _errorMsg!,
                style: const TextStyle(
                    color: AppColors.errorColor, fontSize: 13),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildResultCard() {
    final r = _result!;
    final score = (r['form_score'] as num).toDouble();
    final reps = r['rep_count'] as int;
    final totalFrames = r['total_frames'] as int;
    final badFrames = r['bad_frame_count'] as int;
    final feedback = Map<String, dynamic>.from(r['feedback_summary'] as Map);

    final scoreColor = score >= 80
        ? AppColors.successColor
        : score >= 50
            ? AppColors.warningColor
            : AppColors.errorColor;

    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 20, 24, 0),
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: AppColors.cardBg,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: scoreColor.withOpacity(0.3)),
          boxShadow: [
            BoxShadow(
              color: scoreColor.withOpacity(0.1),
              blurRadius: 20,
              offset: const Offset(0, 6),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Form score hero
            Row(
              children: [
                // Circular score
                SizedBox(
                  width: 80,
                  height: 80,
                  child: Stack(
                    alignment: Alignment.center,
                    children: [
                      SizedBox(
                        width: 80,
                        height: 80,
                        child: CircularProgressIndicator(
                          value: score / 100,
                          strokeWidth: 6,
                          color: scoreColor,
                          backgroundColor: scoreColor.withOpacity(0.15),
                        ),
                      ),
                      Text(
                        '${score.round()}',
                        style: TextStyle(
                          color: scoreColor,
                          fontSize: 24,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 20),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        score >= 80
                            ? 'Great Form! 🔥'
                            : score >= 50
                                ? 'Needs Work 💪'
                                : 'Fix Your Form ⚠️',
                        style: TextStyle(
                          color: scoreColor,
                          fontSize: 18,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        _titleCase(r['exercise_name'] as String),
                        style: const TextStyle(
                          color: AppColors.textMuted,
                          fontSize: 13,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 18),

            // Stats row
            Row(
              children: [
                _statChip('Reps', '$reps', AppColors.primary),
                const SizedBox(width: 10),
                _statChip('Good Frames', '${totalFrames - badFrames}',
                    AppColors.successColor),
                const SizedBox(width: 10),
                _statChip('Bad Frames', '$badFrames', AppColors.errorColor),
              ],
            ),

            // Feedback
            if (feedback.isNotEmpty) ...[
              const SizedBox(height: 18),
              const Text(
                'Feedback',
                style: TextStyle(
                  color: AppColors.textPrimary,
                  fontWeight: FontWeight.w700,
                  fontSize: 14,
                ),
              ),
              const SizedBox(height: 8),
              ...feedback.entries.map((e) => Padding(
                    padding: const EdgeInsets.only(bottom: 6),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.warning_amber_rounded,
                            color: AppColors.warningColor, size: 16),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            '${e.key}  (×${e.value})',
                            style: const TextStyle(
                                color: AppColors.textMuted, fontSize: 12),
                          ),
                        ),
                      ],
                    ),
                  )),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildCorrectionVideoSection() {
    final videoUrl = PoseService.correctionVideoUrl(
        _result!['video_url'] as String);
    final hasPlayer =
        _videoController != null && _videoController!.value.isInitialized;

    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 20, 24, 0),
      child: _section(
        title: 'Correction Video',
        icon: Icons.play_circle_rounded,
        child: Column(
          children: [
            if (hasPlayer)
              ClipRRect(
                borderRadius: BorderRadius.circular(14),
                child: AspectRatio(
                  aspectRatio: _videoController!.value.aspectRatio,
                  child: Stack(
                    alignment: Alignment.center,
                    children: [
                      VideoPlayer(_videoController!),
                      GestureDetector(
                        onTap: () {
                          setState(() {
                            _videoController!.value.isPlaying
                                ? _videoController!.pause()
                                : _videoController!.play();
                          });
                        },
                        child: AnimatedOpacity(
                          opacity:
                              _videoController!.value.isPlaying ? 0.0 : 1.0,
                          duration: const Duration(milliseconds: 200),
                          child: Container(
                            width: 60,
                            height: 60,
                            decoration: const BoxDecoration(
                              color: Colors.black54,
                              shape: BoxShape.circle,
                            ),
                            child: const Icon(Icons.play_arrow_rounded,
                                color: Colors.white, size: 36),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            if (!hasPlayer) ...[
              Container(
                padding: const EdgeInsets.symmetric(vertical: 20),
                decoration: BoxDecoration(
                  color: AppColors.darkBg,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Column(
                  children: [
                    const Icon(Icons.videocam_off_rounded,
                        color: AppColors.textMuted, size: 32),
                    const SizedBox(height: 8),
                    const Text(
                      'Inline playback unavailable',
                      style: TextStyle(
                          color: AppColors.textMuted, fontSize: 13),
                    ),
                    const SizedBox(height: 12),
                    GestureDetector(
                      onTap: () {
                        // Open video URL in browser tab
                        // ignore: avoid_print
                        debugPrint('Open video: $videoUrl');
                      },
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 20, vertical: 10),
                        decoration: BoxDecoration(
                          color: AppColors.primary.withOpacity(0.15),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.download_rounded,
                                color: AppColors.primary, size: 18),
                            const SizedBox(width: 8),
                            Text(
                              'Download Video',
                              style: TextStyle(
                                color: AppColors.primary,
                                fontWeight: FontWeight.w700,
                                fontSize: 13,
                              ),
                            ),
                          ],
                        ),
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

  // ── shared helpers ────────────────────────────────────────────────────
  Widget _section({
    required String title,
    required IconData icon,
    required Widget child,
  }) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardBg,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: const Color(0xFF2E2E3E)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: AppColors.primary, size: 18),
              const SizedBox(width: 8),
              Text(
                title,
                style: const TextStyle(
                  color: AppColors.textPrimary,
                  fontWeight: FontWeight.w700,
                  fontSize: 14,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          child,
        ],
      ),
    );
  }

  Widget _statChip(String label, String value, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 12),
        decoration: BoxDecoration(
          color: color.withOpacity(0.08),
          borderRadius: BorderRadius.circular(12),
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
}
