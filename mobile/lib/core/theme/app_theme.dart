import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  static ThemeData light() {
    const primary = Color(0xFF1E3A2F);
    const secondary = Color(0xFFC38B1C);
    const surface = Color(0xFFF7F3EE);
    const background = Color(0xFFF1ECE6);

    final colorScheme = const ColorScheme.light(
      primary: primary,
      secondary: secondary,
      surface: surface,
      error: Color(0xFFB00020),
    );

    final textTheme = GoogleFonts.plusJakartaSansTextTheme().apply(
      bodyColor: Colors.black87,
      displayColor: Colors.black87,
    );

    return ThemeData(
      colorScheme: colorScheme,
      scaffoldBackgroundColor: background,
      textTheme: textTheme,
      appBarTheme: AppBarTheme(
        backgroundColor: surface,
        foregroundColor: primary,
        elevation: 0,
        titleTextStyle: textTheme.titleLarge?.copyWith(
          fontWeight: FontWeight.w600,
          color: primary,
        ),
      ),
      cardTheme: CardThemeData(
        color: surface,
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Color(0xFFE2DCD4)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: primary, width: 1.4),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primary,
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 20),
        ),
      ),
    );
  }
}
