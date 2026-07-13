import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:gym2/Screens/home_screen.dart';
import 'package:gym2/Screens/flash_screen.dart';
import 'package:gym2/Screens/login_screen.dart';
import 'package:gym2/services/auth_service.dart';
import 'package:gym2/services/dio_helper.dart';
import 'package:gym2/theme.dart';
import 'firebase_options.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);
  DioHelper.init();
  await AuthService().init();
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    final isLoggedIn = AuthService().currentUser != null;

    final Widget initialScreen = isLoggedIn
        ? const HomeScreen()
        : const LoginScreen();

    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'REV FIT AI',
      theme: AppTheme.dark,
      home: SplashScreen(
        imagePath: 'assets/flash.png',
        bottomText: 'revfitai',
        duration: const Duration(seconds: 3),
        nextScreen: initialScreen,
      ),
    );
  }
}
