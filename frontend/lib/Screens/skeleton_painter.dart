// lib/Screens/skeleton_painter.dart
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:gym2/colors/colors.dart';

/// MediaPipe Pose landmark connections for drawing the skeleton.
///
/// Each pair is [startIdx, endIdx] referencing the 33-landmark topology.
const List<List<int>> _poseConnections = [
  // Torso
  [11, 12], // shoulders
  [11, 23], // left shoulder → left hip
  [12, 24], // right shoulder → right hip
  [23, 24], // hips
  // Left arm
  [11, 13], // left shoulder → left elbow
  [13, 15], // left elbow → left wrist
  // Right arm
  [12, 14], // right shoulder → right elbow
  [14, 16], // right elbow → right wrist
  // Left leg
  [23, 25], // left hip → left knee
  [25, 27], // left knee → left ankle
  // Right leg
  [24, 26], // right hip → right knee
  [26, 28], // right knee → right ankle
  // Face (optional)
  [0, 1], [1, 2], [2, 3], [3, 7], // left eye cascade
  [0, 4], [4, 5], [5, 6], [6, 8], // right eye cascade
  [9, 10], // mouth
  // Hands
  [15, 17], [15, 19], [15, 21], // left hand
  [16, 18], [16, 20], [16, 22], // right hand
  // Feet
  [27, 29], [27, 31], // left foot
  [28, 30], [28, 32], // right foot
];

/// Minimum visibility score for a landmark to be drawn.
const double _visibilityThreshold = 0.5;

/// A [CustomPainter] that draws the MediaPipe Pose skeleton on top of a camera
/// preview. Landmarks are normalised to (0–1, 0–1) and scaled to the widget
/// size at paint time.
///
/// Joints are colour-coded:
/// - **Green** when form is good
/// - **Red** when form is bad
///
/// A subtle neon-glow effect is applied via a blurred shadow pass.
class SkeletonPainter extends CustomPainter {
  /// 33-element list of [x, y, visibility], each normalised 0–1.
  final List<List<double>> landmarks;

  /// Whether the current frame has good form overall.
  final bool isGoodForm;

  /// If true, the camera is using the front lens and coordinates should be
  /// mirrored horizontally.
  final bool isFrontCamera;

  SkeletonPainter({
    required this.landmarks,
    required this.isGoodForm,
    this.isFrontCamera = false,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (landmarks.isEmpty) return;

    final accentColor = isGoodForm ? AppColors.successColor : AppColors.errorColor;

    // ── Glow (shadow) pass ───────────────────────────────────────────────
    final glowPaint = Paint()
      ..color = accentColor.withOpacity(0.3)
      ..strokeWidth = 6.0
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8);

    final linePaint = Paint()
      ..color = accentColor
      ..strokeWidth = 3.0
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;

    final jointPaint = Paint()
      ..color = accentColor
      ..style = PaintingStyle.fill;

    final jointBorderPaint = Paint()
      ..color = Colors.white.withOpacity(0.8)
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke;

    // ── Draw connections ─────────────────────────────────────────────────
    for (final conn in _poseConnections) {
      final a = conn[0];
      final b = conn[1];
      if (a >= landmarks.length || b >= landmarks.length) continue;

      final lmA = landmarks[a];
      final lmB = landmarks[b];
      if (lmA.length < 3 || lmB.length < 3) continue;
      if (lmA[2] < _visibilityThreshold || lmB[2] < _visibilityThreshold) {
        continue;
      }

      final pA = _toOffset(lmA, size);
      final pB = _toOffset(lmB, size);

      // Glow pass
      canvas.drawLine(pA, pB, glowPaint);
      // Solid pass
      canvas.drawLine(pA, pB, linePaint);
    }

    // ── Draw joints ─────────────────────────────────────────────────────
    for (int i = 0; i < landmarks.length; i++) {
      final lm = landmarks[i];
      if (lm.length < 3 || lm[2] < _visibilityThreshold) continue;

      // Skip face landmarks for a cleaner look (indices 0-10)
      if (i <= 10) continue;

      final p = _toOffset(lm, size);
      canvas.drawCircle(p, 5, jointPaint);
      canvas.drawCircle(p, 5, jointBorderPaint);
    }
  }

  Offset _toOffset(List<double> lm, Size size) {
    final x = isFrontCamera ? (1.0 - lm[0]) : lm[0];
    final y = lm[1];
    return Offset(x * size.width, y * size.height);
  }

  @override
  bool shouldRepaint(covariant SkeletonPainter oldDelegate) {
    // Always repaint — landmarks change every frame.
    return true;
  }
}
