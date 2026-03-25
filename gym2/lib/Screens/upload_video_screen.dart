import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'package:video_player/video_player.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:image_picker/image_picker.dart' show XFile;
import 'package:gym2/colors/colors.dart';
import 'package:gym2/services/pose_service.dart';

class UploadVideoScreen extends StatefulWidget {
  const UploadVideoScreen({super.key});

  @override
  State<UploadVideoScreen> createState() => _UploadVideoScreenState();
}

class _UploadVideoScreenState extends State<UploadVideoScreen> {
  XFile? _selectedVideo;
  String? _selectedExercise;
  List<String> _exercises = [];
  bool _isUploading = false;
  double _uploadProgress = 0;
  PoseAnalysisResult? _result;
  VideoPlayerController? _videoController;

  @override
  void initState() {
    super.initState();
    _loadExercises();
  }

  @override
  void dispose() {
    _videoController?.dispose();
    super.dispose();
  }

  Future<void> _loadExercises() async {
    try {
      final list = await PoseService.getExercises();
      if (mounted) {
        setState(() {
          _exercises = list;
          if (_exercises.isNotEmpty) _selectedExercise = _exercises.first;
        });
      }
    } catch (e) {
      if (mounted) {
        _showError('Failed to load exercises: Start your backend first!');
      }
    }
  }

  Future<void> _pickVideo() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.video,
      withData: kIsWeb, // Needed for web
    );
    
    if (result != null) {
      final file = result.files.single;
      setState(() {
        if (kIsWeb) {
          _selectedVideo = XFile.fromData(file.bytes!, name: file.name);
        } else {
          _selectedVideo = XFile(file.path!);
        }
        _result = null; // Clear old results
      });
      _playPreview();
    }
  }

  void _playPreview() {
    _videoController?.dispose();
    if (_selectedVideo != null) {
      if (kIsWeb) {
        // Use blob/network URL for web preview
        _videoController = VideoPlayerController.networkUrl(Uri.parse(_selectedVideo!.path))
          ..initialize().then((_) {
            if (mounted) setState(() {});
            _videoController!.play();
            _videoController!.setLooping(true);
          });
      } else {
        _videoController = VideoPlayerController.contentUri(Uri.parse(_selectedVideo!.path))
          ..initialize().then((_) {
            if (mounted) setState(() {});
            _videoController!.play();
            _videoController!.setLooping(true);
          });
      }
    }
  }

  Future<void> _analyzeVideo() async {
    if (_selectedVideo == null || _selectedExercise == null) return;

    setState(() {
      _isUploading = true;
      _uploadProgress = 0;
      _result = null;
    });

    try {
      final result = await PoseService.analyzeVideo(
        videoFile: _selectedVideo!,
        exerciseName: _selectedExercise!,
        onSendProgress: (progress) => setState(() => _uploadProgress = progress),
      );

      setState(() {
        _result = result;
        _isUploading = false;
      });

      // Load the annotated video from the backend
      final url = PoseService.videoDownloadUrl(result.sessionId);
      _videoController?.dispose();
      _videoController = VideoPlayerController.networkUrl(Uri.parse(url))
        ..initialize().then((_) {
          if (mounted) setState(() {});
          _videoController!.play();
          _videoController!.setLooping(true);
        });
    } catch (e) {
      setState(() {
        _isUploading = false;
      });
      _showError(e.toString());
    }
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: AppColors.errorColor),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.backgroundColor,
      appBar: AppBar(
        title: const Text('Pose AI Analysis', style: TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _buildExerciseSelector(),
            const SizedBox(height: 20),
            _buildVideoSlot(),
            const SizedBox(height: 20),
            if (_isUploading) _buildProgressBar() else _buildActionButtons(),
            if (_result != null) ...[
              const SizedBox(height: 30),
              _buildResultsDashboard(),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildExerciseSelector() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(15),
        border: Border.all(color: AppColors.primary.withOpacity(0.3)),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          value: _selectedExercise,
          dropdownColor: AppColors.surface,
          hint: const Text('Select Exercise', style: TextStyle(color: AppColors.textMuted)),
          style: const TextStyle(color: AppColors.textPrimary, fontSize: 16),
          isExpanded: true,
          items: _exercises.map((String value) {
            return DropdownMenuItem<String>(
              value: value,
              child: Text(value.toUpperCase()),
            );
          }).toList(),
          onChanged: (newValue) => setState(() => _selectedExercise = newValue),
        ),
      ),
    );
  }

  Widget _buildVideoSlot() {
    final hasVideo = _videoController != null && _videoController!.value.isInitialized;

    return AspectRatio(
      aspectRatio: 16 / 9,
      child: Container(
        decoration: BoxDecoration(
          color: AppColors.cardBg,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: AppColors.textDisabled, width: 1),
        ),
        clipBehavior: Clip.antiAlias,
        child: hasVideo
            ? VideoPlayer(_videoController!)
            : InkWell(
                onTap: _pickVideo,
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.movie_creation_outlined, size: 50, color: AppColors.primary.withOpacity(0.5)),
                    const SizedBox(height: 10),
                    const Text('Tap to choose exercise video', style: TextStyle(color: AppColors.textMuted)),
                  ],
                ),
              ),
      ),
    );
  }

  Widget _buildProgressBar() {
    return Column(
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(10),
          child: LinearProgressIndicator(
            value: _uploadProgress,
            backgroundColor: AppColors.surface,
            color: AppColors.primary,
            minHeight: 12,
          ),
        ),
        const SizedBox(height: 10),
        Text(
          'Uploading & Analyzing Video... ${(_uploadProgress * 100).toInt()}%',
          style: const TextStyle(color: AppColors.textMuted),
        ),
      ],
    );
  }

  Widget _buildActionButtons() {
    return Row(
      children: [
        Expanded(
          child: ElevatedButton.icon(
            onPressed: _pickVideo,
            icon: const Icon(Icons.video_library),
            label: const Text('CHANGE VIDEO'),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.surface,
              foregroundColor: AppColors.textPrimary,
              padding: const EdgeInsets.symmetric(vertical: 15),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
          ),
        ),
        const SizedBox(width: 15),
        Expanded(
          flex: 2,
          child: ElevatedButton.icon(
            onPressed: (_selectedVideo != null && !_isUploading) ? _analyzeVideo : null,
            icon: const Icon(Icons.bolt, color: Colors.white),
            label: const Text('START ANALYSIS', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.primary,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 15),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              elevation: 4,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildResultsDashboard() {
    final res = _result!;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('ANALYSIS SUMMARY', style: TextStyle(color: AppColors.primary, fontWeight: FontWeight.bold, letterSpacing: 1.2)),
        const SizedBox(height: 15),
        Row(
          children: [
            _buildStatCard('REPS', res.repCount.toString(), Icons.repeat),
            const SizedBox(width: 15),
            _buildStatCard('FORM SCORE', '${res.goodFormPercent.toInt()}%', Icons.verified_user_outlined, color: res.goodFormPercent > 70 ? AppColors.successColor : AppColors.warningColor),
          ],
        ),
        const SizedBox(height: 20),
        const Text('FORM FEEDBACK', style: TextStyle(color: AppColors.textMuted, fontSize: 12, fontWeight: FontWeight.bold)),
        const SizedBox(height: 10),
        if (res.feedbacks.isEmpty)
          const Text('Perfect form! No improvements needed.', style: TextStyle(color: AppColors.successColor))
        else
          ...res.feedbacks.map((f) => _buildFeedbackTile(f)),
      ],
    );
  }

  Widget _buildStatCard(String label, String value, IconData icon, {Color? color}) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(15),
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(15),
          border: Border.all(color: (color ?? AppColors.primary).withOpacity(0.2)),
        ),
        child: Column(
          children: [
            Icon(icon, color: color ?? AppColors.primary, size: 20),
            const SizedBox(height: 8),
            Text(value, style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: color ?? AppColors.textPrimary)),
            Text(label, style: const TextStyle(fontSize: 10, color: AppColors.textMuted)),
          ],
        ),
      ),
    );
  }

  Widget _buildFeedbackTile(PoseFeedback f) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.cardBg,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Icon(Icons.warning_amber_rounded, color: AppColors.errorColor, size: 20),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(f.message, style: const TextStyle(color: AppColors.textPrimary, fontWeight: FontWeight.w500)),
                Text('Detected ${f.occurrenceCount} times', style: const TextStyle(color: AppColors.textMuted, fontSize: 11)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
