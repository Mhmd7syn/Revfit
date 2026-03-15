// live_camera_screen.dart
import 'package:flutter/material.dart';
import 'package:gym2/colors/colors.dart';

class LiveCameraScreen extends StatelessWidget {
  const LiveCameraScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Live Camera'),
        backgroundColor: AppColors.backgroundColor,
        foregroundColor: AppColors.primaryColor,
      ),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.videocam,
              size: 80,
              color: AppColors.primaryColor.withOpacity(0.3),
            ),
            const SizedBox(height: 20),
            Text(
              'Live camera feed will appear here.',
              style: TextStyle(fontSize: 18, color: AppColors.primaryColor),
            ),
            const SizedBox(height: 10),
            Text(
              '(Camera implementation coming soon)',
              style: TextStyle(
                fontSize: 14,
                color: AppColors.primaryColor.withOpacity(0.6),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
