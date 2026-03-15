import 'package:flutter/material.dart';

final class AppColors {
  // ── Backgrounds ─────────────────────────────────────────────────────────
  static const Color darkBg = Color(0xFF0D0D0D);
  static const Color surface = Color(0xFF1A1A2E);
  static const Color surfaceAlt = Color(0xFF16213E);
  static const Color cardBg = Color(0xFF1E1E2E);

  // ── Accents ──────────────────────────────────────────────────────────────
  static const Color primary = Color(0xFFFF6B35);
  static const Color primaryLight = Color(0xFFFF8C5A);
  static const Color primaryDark = Color(0xFFE55520);
  static const Color secondary = Color(0xFF4ECDC4);
  static const Color secondaryDark = Color(0xFF38A39B);
  static const Color accent3 = Color(0xFFC084FC); // purple highlight

  // ── Text ─────────────────────────────────────────────────────────────────
  static const Color textPrimary = Color(0xFFF5F5F5);
  static const Color textMuted = Color(0xFF9E9E9E);
  static const Color textDisabled = Color(0xFF555555);

  // ── Status ───────────────────────────────────────────────────────────────
  static const Color errorColor = Color(0xFFCF6679);
  static const Color successColor = Color(0xFF4CAF86);
  static const Color warningColor = Color(0xFFFFB938);

  // ── Legacy aliases (keeps old references working) ────────────────────────
  static const Color backgroundColor = darkBg;
  static const Color primaryColor = primary;

  // ── Gradients ────────────────────────────────────────────────────────────
  static const LinearGradient primaryGradient = LinearGradient(
    colors: [primary, primaryLight],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const LinearGradient darkGradient = LinearGradient(
    colors: [darkBg, surfaceAlt],
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
  );

  static const LinearGradient heroGradient = LinearGradient(
    colors: [Color(0xFF0D0D0D), Color(0xFF1A1A2E), Color(0xFF16213E)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );
}
