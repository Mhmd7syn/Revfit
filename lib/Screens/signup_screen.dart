// lib/screens/signup_screen.dart
import 'package:flutter/material.dart';
import 'package:gym2/colors/colors.dart';
import 'package:gym2/services/auth_service.dart';
import 'package:gym2/models/user_model.dart';
import 'package:gym2/constants/app_constants.dart';
import 'home_screen.dart';
import 'login_screen.dart';

class SignupScreen extends StatefulWidget {
  const SignupScreen({super.key});

  @override
  State<SignupScreen> createState() => _SignupScreenState();
}

class _SignupScreenState extends State<SignupScreen>
    with TickerProviderStateMixin {
  final _formKeys = [
    GlobalKey<FormState>(),
    GlobalKey<FormState>(),
    GlobalKey<FormState>(),
  ];

  final AuthService _authService = AuthService();

  // Controllers
  final _nameController = TextEditingController();
  final _emailController = TextEditingController();
  final _phoneController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();
  final _heightController = TextEditingController();
  final _weightController = TextEditingController();
  final _ageController = TextEditingController();

  // State
  String? _selectedGender;
  String? _selectedGoal;
  bool _isVegetarian = false;
  bool _obscurePassword = true;
  bool _obscureConfirm = true;
  bool _isLoading = false;
  int _currentStep = 0;

  final List<String> _genders = ['Male', 'Female', 'Other'];
  final List<String> _goals = [
    'Lose Weight (Fat Loss)',
    'Build Muscle (Bulking)',
    'Increase Strength',
    'Improve Endurance',
    'Tone & Maintain',
  ];

  late final AnimationController _slideCtrl;
  late final Animation<Offset> _slideAnim;

  @override
  void initState() {
    super.initState();
    _slideCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    )..forward();
    _slideAnim = Tween<Offset>(begin: const Offset(0, 0.1), end: Offset.zero)
        .animate(CurvedAnimation(parent: _slideCtrl, curve: Curves.easeOut));
  }

  @override
  void dispose() {
    _slideCtrl.dispose();
    _nameController.dispose();
    _emailController.dispose();
    _phoneController.dispose();
    _passwordController.dispose();
    _confirmPasswordController.dispose();
    _heightController.dispose();
    _weightController.dispose();
    _ageController.dispose();
    super.dispose();
  }

  // ── Helpers ──────────────────────────────────────────────────────────────

  String _mapGoalToType(String? goal) {
    if (goal == null) return 'maintenance';
    if (goal.contains('Lose Weight') || goal.contains('Fat Loss')) {
      return 'fat_loss';
    }
    if (goal.contains('Build Muscle') || goal.contains('Bulking')) {
      return 'muscle_gain';
    }
    if (goal.contains('Endurance')) return 'endurance';
    if (goal.contains('Strength')) return 'strength';
    return 'maintenance';
  }

  double? _calculateBmi(double? height, double? weight) {
    if (height == null || weight == null || height <= 0) return null;
    final heightM = height / 100.0;
    return double.parse((weight / (heightM * heightM)).toStringAsFixed(1));
  }

  String _derivedDietType() => _isVegetarian ? 'vegetarian' : 'omnivore';

  void _nextStep() {
    if (!_formKeys[_currentStep].currentState!.validate()) return;
    if (_currentStep == 1 &&
        (_selectedGender == null)) {
      _showError('Please select your gender');
      return;
    }
    if (_currentStep < 2) {
      setState(() => _currentStep++);
      _slideCtrl.forward(from: 0);
    } else {
      _signUp();
    }
  }

  void _prevStep() {
    if (_currentStep > 0) setState(() => _currentStep--);
  }

  void _showError(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg),
        backgroundColor: AppColors.errorColor,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    );
  }

  Future<void> _signUp() async {
    if (_selectedGoal == null) {
      _showError('Please select your fitness goal');
      return;
    }

    setState(() => _isLoading = true);

    try {
      final age = int.parse(_ageController.text.trim());
      final height = double.tryParse(_heightController.text.trim());
      final weight = double.tryParse(_weightController.text.trim());
      final bmi = _calculateBmi(height, weight);

      final userModel = UserModel(
        uid: '',
        name: _nameController.text.trim(),
        email: _emailController.text.trim(),
        phone: _phoneController.text.trim(),
        age: age,
        gender: _selectedGender!,
        height: height ?? 0,
        weight: weight ?? 0,
        goal: _selectedGoal!,
        isVegetarian: _isVegetarian,
        goalType: _mapGoalToType(_selectedGoal),
        bmi: bmi,
        defaultDietType: _derivedDietType(),
      );

      final error = await _authService.signUpWithEmail(
        email: _emailController.text.trim(),
        password: _passwordController.text.trim(),
        userModel: userModel,
      );

      if (!mounted) return;

      if (error == null) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: const Text('Account created! Please verify your email.'),
            backgroundColor: AppColors.successColor,
            behavior: SnackBarBehavior.floating,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          ),
        );
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(builder: (_) => const HomeScreen()),
        );
      } else {
        _showError(error);
      }
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  // ── Build ─────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: AppColors.heroGradient),
        child: SafeArea(
          child: Column(
            children: [
              _buildHeader(),
              _buildProgressBar(),
              Expanded(
                child: SlideTransition(
                  position: _slideAnim,
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.fromLTRB(28, 16, 28, 24),
                    child: _buildCurrentStep(),
                  ),
                ),
              ),
              _buildNavButtons(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    final titles = [
      'Personal Info',
      'Body Details',
      'Fitness Goals',
    ];
    final subtitles = [
      'Tell us who you are',
      'Help us personalize your plan',
      'What do you want to achieve?',
    ];

    return Padding(
      padding: const EdgeInsets.fromLTRB(28, 20, 28, 8),
      child: Row(
        children: [
          if (_currentStep > 0)
            GestureDetector(
              onTap: _prevStep,
              child: Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: AppColors.cardBg,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: const Color(0xFF2E2E3E)),
                ),
                child: const Icon(Icons.arrow_back_ios_new_rounded, size: 16),
              ),
            )
          else
            GestureDetector(
              onTap: () => Navigator.maybePop(context),
              child: Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: AppColors.cardBg,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: const Color(0xFF2E2E3E)),
                ),
                child: const Icon(Icons.arrow_back_ios_new_rounded, size: 16),
              ),
            ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  titles[_currentStep],
                  style: const TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 22,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                Text(
                  subtitles[_currentStep],
                  style: const TextStyle(
                    color: AppColors.textMuted,
                    fontSize: 13,
                  ),
                ),
              ],
            ),
          ),
          Text(
            '${_currentStep + 1}/3',
            style: const TextStyle(
              color: AppColors.primary,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildProgressBar() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 12),
      child: Row(
        children: List.generate(3, (i) {
          final isActive = i <= _currentStep;
          return Expanded(
            child: Container(
              height: 4,
              margin: EdgeInsets.only(right: i < 2 ? 6 : 0),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(4),
                gradient: isActive
                    ? const LinearGradient(
                        colors: [AppColors.primary, AppColors.primaryLight],
                      )
                    : null,
                color: isActive ? null : const Color(0xFF2E2E3E),
              ),
            ),
          );
        }),
      ),
    );
  }

  Widget _buildCurrentStep() {
    switch (_currentStep) {
      case 0:
        return _buildStep1();
      case 1:
        return _buildStep2();
      case 2:
        return _buildStep3();
      default:
        return const SizedBox.shrink();
    }
  }

  Widget _buildGlassCard({required Widget child}) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.cardBg.withOpacity(0.85),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: const Color(0xFF2E2E3E)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.25),
            blurRadius: 20,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: child,
    );
  }

  // Step 1 – Personal info
  Widget _buildStep1() {
    return _buildGlassCard(
      child: Form(
        key: _formKeys[0],
        child: Column(
          children: [
            _field(
              controller: _nameController,
              label: 'Full Name',
              icon: Icons.person_outline_rounded,
              validator: (v) => v == null || v.isEmpty ? 'Enter your name' : null,
            ),
            const SizedBox(height: 14),
            _field(
              controller: _emailController,
              label: 'Email address',
              icon: Icons.email_outlined,
              keyboardType: TextInputType.emailAddress,
              validator: (v) {
                if (v == null || v.isEmpty) return 'Enter email';
                if (!RegExp(r'^[^@]+@[^@]+\.[^@]+').hasMatch(v)) {
                  return 'Invalid email';
                }
                return null;
              },
            ),
            const SizedBox(height: 14),
            _field(
              controller: _phoneController,
              label: 'Phone number',
              icon: Icons.phone_outlined,
              keyboardType: TextInputType.phone,
              validator: (v) {
                if (v == null || v.isEmpty) return 'Enter phone';
                if (!RegExp(r'^[0-9]{10,15}$').hasMatch(v)) {
                  return 'Invalid phone number';
                }
                return null;
              },
            ),
            const SizedBox(height: 14),
            _field(
              controller: _passwordController,
              label: 'Password',
              icon: Icons.lock_outlined,
              obscure: _obscurePassword,
              suffixIcon: IconButton(
                icon: Icon(
                  _obscurePassword
                      ? Icons.visibility_outlined
                      : Icons.visibility_off_outlined,
                  size: 20,
                  color: AppColors.textMuted,
                ),
                onPressed: () =>
                    setState(() => _obscurePassword = !_obscurePassword),
              ),
              validator: (v) {
                if (v == null || v.isEmpty) return 'Enter password';
                if (!RegExp(r'^(?=.*[A-Z])(?=.*\d).{8,}$').hasMatch(v)) {
                  return '8+ chars, 1 uppercase, 1 number';
                }
                return null;
              },
            ),
            const SizedBox(height: 14),
            _field(
              controller: _confirmPasswordController,
              label: 'Confirm password',
              icon: Icons.lock_outline_rounded,
              obscure: _obscureConfirm,
              suffixIcon: IconButton(
                icon: Icon(
                  _obscureConfirm
                      ? Icons.visibility_outlined
                      : Icons.visibility_off_outlined,
                  size: 20,
                  color: AppColors.textMuted,
                ),
                onPressed: () =>
                    setState(() => _obscureConfirm = !_obscureConfirm),
              ),
              validator: (v) => v != _passwordController.text
                  ? "Passwords don't match"
                  : null,
            ),
          ],
        ),
      ),
    );
  }

  // Step 2 – Body info
  Widget _buildStep2() {
    final h = double.tryParse(_heightController.text);
    final w = double.tryParse(_weightController.text);
    final bmi = _calculateBmi(h, w);

    return _buildGlassCard(
      child: Form(
        key: _formKeys[1],
        child: Column(
          children: [
            _field(
              controller: _ageController,
              label: 'Age',
              icon: Icons.cake_outlined,
              keyboardType: TextInputType.number,
              validator: (v) {
                if (v == null || v.isEmpty) return 'Enter age';
                final age = int.tryParse(v);
                if (age == null || age < 1 || age > 120) {
                  return 'Age must be 1–120';
                }
                return null;
              },
            ),
            const SizedBox(height: 14),

            // Gender chips
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Gender',
                  style: TextStyle(color: AppColors.textMuted, fontSize: 13),
                ),
                const SizedBox(height: 10),
                Row(
                  children: _genders.map((g) {
                    final sel = _selectedGender == g;
                    return Expanded(
                      child: GestureDetector(
                        onTap: () => setState(() => _selectedGender = g),
                        child: AnimatedContainer(
                          duration: const Duration(milliseconds: 200),
                          margin: EdgeInsets.only(
                            right: g != _genders.last ? 8 : 0,
                          ),
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          decoration: BoxDecoration(
                            gradient: sel
                                ? const LinearGradient(
                                    colors: [
                                      AppColors.primary,
                                      AppColors.primaryLight
                                    ],
                                  )
                                : null,
                            color: sel ? null : const Color(0xFF2A2A3E),
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(
                              color: sel
                                  ? AppColors.primary
                                  : const Color(0xFF3A3A4E),
                            ),
                          ),
                          child: Text(
                            g,
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              color:
                                  sel ? Colors.white : AppColors.textMuted,
                              fontWeight: FontWeight.w600,
                              fontSize: 13,
                            ),
                          ),
                        ),
                      ),
                    );
                  }).toList(),
                ),
              ],
            ),

            const SizedBox(height: 14),

            Row(
              children: [
                Expanded(
                  child: _field(
                    controller: _heightController,
                    label: 'Height (cm)',
                    icon: Icons.height_rounded,
                    keyboardType: TextInputType.number,
                    onChanged: (_) => setState(() {}),
                    validator: (v) {
                      if (v == null || v.isEmpty) return 'Required';
                      if ((double.tryParse(v) ?? 0) <= 0) {
                        return 'Invalid';
                      }
                      return null;
                    },
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _field(
                    controller: _weightController,
                    label: 'Weight (kg)',
                    icon: Icons.monitor_weight_outlined,
                    keyboardType: TextInputType.number,
                    onChanged: (_) => setState(() {}),
                    validator: (v) {
                      if (v == null || v.isEmpty) return 'Required';
                      if ((double.tryParse(v) ?? 0) <= 0) {
                        return 'Invalid';
                      }
                      return null;
                    },
                  ),
                ),
              ],
            ),

            if (bmi != null) ...[
              const SizedBox(height: 14),
              _buildBmiChip(bmi),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildBmiChip(double bmi) {
    String category;
    Color color;
    if (bmi < 18.5) {
      category = 'Underweight';
      color = AppColors.secondary;
    } else if (bmi < 25) {
      category = 'Normal';
      color = AppColors.successColor;
    } else if (bmi < 30) {
      category = 'Overweight';
      color = AppColors.warningColor;
    } else {
      category = 'Obese';
      color = AppColors.errorColor;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.35)),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.monitor_weight_outlined, color: color, size: 18),
          const SizedBox(width: 10),
          Text(
            'BMI: $bmi  ·  $category',
            style: TextStyle(
              color: color,
              fontWeight: FontWeight.w700,
              fontSize: 14,
            ),
          ),
        ],
      ),
    );
  }

  // Step 3 – Fitness goals
  Widget _buildStep3() {
    return _buildGlassCard(
      child: Form(
        key: _formKeys[2],
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Primary Goal',
              style: TextStyle(color: AppColors.textMuted, fontSize: 13),
            ),
            const SizedBox(height: 10),
            ..._goals.map((g) {
              final sel = _selectedGoal == g;
              return GestureDetector(
                onTap: () => setState(() => _selectedGoal = g),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 180),
                  margin: const EdgeInsets.only(bottom: 10),
                  padding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 14,
                  ),
                  decoration: BoxDecoration(
                    gradient: sel
                        ? const LinearGradient(
                            colors: [
                              AppColors.primary,
                              AppColors.primaryLight
                            ],
                            begin: Alignment.centerLeft,
                            end: Alignment.centerRight,
                          )
                        : null,
                    color: sel ? null : const Color(0xFF2A2A3E),
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(
                      color: sel
                          ? AppColors.primary
                          : const Color(0xFF3A3A4E),
                    ),
                    boxShadow: sel
                        ? [
                            BoxShadow(
                              color: AppColors.primary.withOpacity(0.25),
                              blurRadius: 12,
                              offset: const Offset(0, 4),
                            ),
                          ]
                        : [],
                  ),
                  child: Row(
                    children: [
                      Icon(
                        _goalIcon(g),
                        color: sel ? Colors.white : AppColors.textMuted,
                        size: 20,
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Text(
                          g,
                          style: TextStyle(
                            color: sel
                                ? Colors.white
                                : AppColors.textPrimary,
                            fontWeight: FontWeight.w600,
                            fontSize: 14,
                          ),
                        ),
                      ),
                      if (sel)
                        const Icon(
                          Icons.check_circle_rounded,
                          color: Colors.white,
                          size: 18,
                        ),
                    ],
                  ),
                ),
              );
            }),

            const SizedBox(height: 8),
            const Divider(color: Color(0xFF2E2E3E)),
            const SizedBox(height: 8),

            // Vegetarian toggle
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Vegetarian diet',
                        style: TextStyle(
                          color: AppColors.textPrimary,
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        'Affects your personalized meal plan',
                        style: TextStyle(
                          color: AppColors.textMuted,
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ),
                ),
                Switch.adaptive(
                  value: _isVegetarian,
                  onChanged: (v) => setState(() => _isVegetarian = v),
                  activeColor: AppColors.primary,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  IconData _goalIcon(String goal) {
    if (goal.contains('Lose')) return Icons.local_fire_department_rounded;
    if (goal.contains('Muscle') || goal.contains('Bulking')) {
      return Icons.fitness_center_rounded;
    }
    if (goal.contains('Strength')) return Icons.bolt_rounded;
    if (goal.contains('Endurance')) return Icons.directions_run_rounded;
    return Icons.self_improvement_rounded;
  }

  Widget _buildNavButtons() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(28, 8, 28, 24),
      child: Column(
        children: [
          _isLoading
              ? _buildLoadingButton()
              : GestureDetector(
                  onTap: _nextStep,
                  child: Container(
                    width: double.infinity,
                    height: 54,
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        colors: [AppColors.primary, AppColors.primaryLight],
                        begin: Alignment.centerLeft,
                        end: Alignment.centerRight,
                      ),
                      borderRadius: BorderRadius.circular(14),
                      boxShadow: [
                        BoxShadow(
                          color: AppColors.primary.withOpacity(0.4),
                          blurRadius: 16,
                          offset: const Offset(0, 6),
                        ),
                      ],
                    ),
                    child: Center(
                      child: Text(
                        _currentStep == 2 ? 'Create Account 🚀' : 'Continue',
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 0.5,
                        ),
                      ),
                    ),
                  ),
                ),
          const SizedBox(height: 14),
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Text(
                'Already have an account? ',
                style: TextStyle(color: AppColors.textMuted, fontSize: 13),
              ),
              GestureDetector(
                onTap: () => Navigator.pushReplacement(
                  context,
                  MaterialPageRoute(builder: (_) => const LoginScreen()),
                ),
                child: const Text(
                  'Sign In',
                  style: TextStyle(
                    color: AppColors.primary,
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildLoadingButton() {
    return Container(
      width: double.infinity,
      height: 54,
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [AppColors.primary, AppColors.primaryLight],
        ),
        borderRadius: BorderRadius.circular(14),
      ),
      child: const Center(
        child: SizedBox(
          width: 24,
          height: 24,
          child: CircularProgressIndicator(
            strokeWidth: 2.5,
            valueColor: AlwaysStoppedAnimation(Colors.white),
          ),
        ),
      ),
    );
  }

  Widget _field({
    required TextEditingController controller,
    required String label,
    required IconData icon,
    TextInputType? keyboardType,
    bool obscure = false,
    Widget? suffixIcon,
    String? Function(String?)? validator,
    void Function(String)? onChanged,
  }) {
    return TextFormField(
      controller: controller,
      keyboardType: keyboardType,
      obscureText: obscure,
      style: const TextStyle(color: AppColors.textPrimary, fontSize: 14),
      onChanged: onChanged,
      decoration: InputDecoration(
        labelText: label,
        prefixIcon: Icon(icon, size: 20),
        suffixIcon: suffixIcon,
      ),
      validator: validator,
    );
  }
}
