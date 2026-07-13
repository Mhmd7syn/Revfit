// upload_video_screen.dart
import 'package:flutter/material.dart';
import 'package:gym2/colors/colors.dart';

class UploadVideoScreen extends StatelessWidget {
  const UploadVideoScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Upload Video'),
        backgroundColor: AppColors.backgroundColor,
        foregroundColor: AppColors.primaryColor,
      ),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.upload_file,
              size: 80,
              color: AppColors.primaryColor.withOpacity(0.3),
            ),
            const SizedBox(height: 20),
            Text(
              'Upload video screen will appear here.',
              style: TextStyle(fontSize: 18, color: AppColors.primaryColor),
            ),
            const SizedBox(height: 10),
            Text(
              '(File picker implementation coming soon)',
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
