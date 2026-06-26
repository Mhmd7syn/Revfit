// lib/screens/workout_plan_screen.dart
import 'package:flutter/material.dart';
import 'package:gym2/colors/colors.dart';
import 'package:gym2/services/auth_service.dart';
import 'package:gym2/services/recommendation_service.dart';
import 'package:gym2/models/workout_plan_model.dart';
import 'package:gym2/models/user_model.dart';

class WorkoutPlanScreen extends StatefulWidget {
  const WorkoutPlanScreen({super.key});

  @override
  State<WorkoutPlanScreen> createState() => _WorkoutPlanScreenState();
}

class _WorkoutPlanScreenState extends State<WorkoutPlanScreen>
    with TickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();
  final AuthService _authService = AuthService();
  final RecommendationService _recommendationService = RecommendationService();

  // Form state
  String? _experienceLevel;
  String? _activityLevel;
  String? _workoutLocation;
  final List<String> _selectedEquipment = [];
  int? _daysPerWeek;
  String? _workoutDuration;
  String? _cardioStrengthBias;
  final _locationController = TextEditingController();

  bool _isGenerating = false;
  WorkoutPlanModel? _generatedPlan;
  String? _errorMessage;
  String? _sessionId;

  // Options
  final List<String> _experienceLevels = ['Beginner', 'Intermediate', 'Expert'];
  final List<String> _activityLevels = [
    'sedentary',
    'light',
    'moderate',
    'active',
    'very_active',
  ];
  final List<String> _workoutLocations = ['home', 'gym', 'both'];
  final List<String> _equipmentOptions = [
    'Body Only',
    'Dumbbell',
    'Barbell',
    'Kettlebells',
    'Cable',
    'Machine',
    'Bands',
    'Medicine Ball',
    'Exercise Ball',
    'Foam Roll',
    'Other',
  ];
  final List<String> _workoutDurations = ['short', 'medium', 'long'];
  final List<String> _cardioStrengthBiases = ['cardio', 'balanced', 'strength'];

  late final AnimationController _resultCtrl;

  @override
  void initState() {
    super.initState();
    _resultCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 500),
    );
  }

  @override
  void dispose() {
    _locationController.dispose();
    _resultCtrl.dispose();
    super.dispose();
  }

  // ── API ──────────────────────────────────────────────────────────────────

  Future<void> _generatePlan() async {
    if (!_formKey.currentState!.validate()) return;
    if (_selectedEquipment.isEmpty) {
      _showError('Please select at least one equipment type');
      return;
    }

    final user = _authService.currentUser;
    if (user == null) {
      _showError('User not logged in');
      return;
    }

    setState(() {
      _isGenerating = true;
      _errorMessage = null;
      _generatedPlan = null;
    });

    try {
      final payload = _buildPayload(user);
      _sessionId ??= await _recommendationService.createSession(payload);

      final planData = await _recommendationService.getStructuredWorkoutPlan(
        _sessionId!,
        topK: _daysPerWeek ?? 5,
      );

      if (!mounted) return;

      final plan = WorkoutPlanModel.fromStructuredApi(
        planData,
        fitnessLevel: _experienceLevel ?? 'Beginner',
      );
      setState(() {
        _generatedPlan = plan;
        _isGenerating = false;
      });
      _resultCtrl.forward(from: 0);
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _errorMessage = 'Failed: ${e.toString()}';
        _isGenerating = false;
      });
    }
  }

  String _sanitizeSex(String gender) {
    final g = gender.toLowerCase();
    if (g == 'male' || g == 'female') return g;
    return 'male'; // API only accepts male/female
  }

  String _sanitizeGoalType(String? goalType) {
    const valid = {'fat_loss', 'muscle_gain', 'maintenance', 'endurance'};
    if (valid.contains(goalType)) return goalType!;
    if (goalType == null) return 'maintenance';
    if (goalType.contains('strength')) return 'muscle_gain';
    if (goalType.contains('tone')) return 'maintenance';
    return 'maintenance';
  }

  Map<String, dynamic> _buildPayload(UserModel user) => {
        'age': user.age,
        'height_cm': user.height,
        'weight_kg': user.weight,
        'sex': _sanitizeSex(user.gender),
        'goal_type': _sanitizeGoalType(user.goalType),
        'fitness_level': _experienceLevel?.toLowerCase() ?? 'beginner',
        'activity_level': _activityLevel ?? 'light',
        'workout_location': _workoutLocation ?? 'both',
        'available_equipment':
            _selectedEquipment.map((e) => e.toLowerCase()).toList(),
        'diet_type': 'omnivore',
        'allergies': [],
        'intolerances': [],
        'country': _locationController.text.trim(),
        'preferred_workout_duration': _workoutDuration ?? 'medium',
        'cardio_strength_bias': _cardioStrengthBias ?? 'balanced',
        'meals_per_day': 3,
        'cooking_time_preference': 'flexible',
        'protein_focus': 'medium',
      };

  void _showError(String msg) {
    setState(() => _errorMessage = msg);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg),
        backgroundColor: AppColors.errorColor,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    );
  }

  // ── Build ─────────────────────────────────────────────────────────────────

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
              child: Column(
                children: [
                  _buildAppBar(),
                  Expanded(
                    child: _generatedPlan != null
                        ? _buildResultView()
                        : _buildFormView(),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildAppBar() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
      child: Row(
        children: [
          GestureDetector(
            onTap: () {
              if (_generatedPlan != null) {
                setState(() {
                  _generatedPlan = null;
                  _sessionId = null;
                });
              } else {
                Navigator.maybePop(context);
              }
            },
            child: Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: AppColors.cardBg,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFF2E2E3E)),
              ),
              child: const Icon(Icons.arrow_back_ios_new_rounded,
                  size: 15, color: AppColors.textMuted),
            ),
          ),
          const SizedBox(width: 14),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Workout Plan',
                  style: TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                Text(
                  'AI-powered personalized program',
                  style: TextStyle(color: AppColors.textMuted, fontSize: 12),
                ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: AppColors.primary.withOpacity(0.15),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: AppColors.primary.withOpacity(0.3)),
            ),
            child: const Icon(Icons.fitness_center_rounded,
                color: AppColors.primary, size: 18),
          ),
        ],
      ),
    );
  }

  // ── Form View ─────────────────────────────────────────────────────────────

  Widget _buildFormView() {
    return Form(
      key: _formKey,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
        physics: const BouncingScrollPhysics(),
        children: [
          // User card
          _buildUserInfoCard(),
          const SizedBox(height: 16),

          // Experience + Activity
          _buildSection(
            title: 'Fitness Profile',
            icon: Icons.person_outline_rounded,
            child: Column(
              children: [
                _buildDropdown<String>(
                  label: 'Experience Level',
                  value: _experienceLevel,
                  items: _experienceLevels,
                  display: (e) => e,
                  onChanged: (v) => setState(() => _experienceLevel = v),
                  validator: (v) =>
                      v == null ? 'Select experience level' : null,
                ),
                const SizedBox(height: 12),
                _buildDropdown<String>(
                  label: 'Activity Level',
                  value: _activityLevel,
                  items: _activityLevels,
                  display: (e) => e.replaceAll('_', ' ').toUpperCase()[0] +
                      e.replaceAll('_', ' ').substring(1),
                  onChanged: (v) => setState(() => _activityLevel = v),
                  validator: (v) =>
                      v == null ? 'Select activity level' : null,
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),

          // Location + Country
          _buildSection(
            title: 'Workout Setup',
            icon: Icons.location_on_outlined,
            child: Column(
              children: [
                _buildDropdown<String>(
                  label: 'Workout Location',
                  value: _workoutLocation,
                  items: _workoutLocations,
                  display: (e) =>
                      '${e[0].toUpperCase()}${e.substring(1)}',
                  onChanged: (v) => setState(() => _workoutLocation = v),
                  validator: (v) =>
                      v == null ? 'Select workout location' : null,
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _locationController,
                  style: const TextStyle(
                      color: AppColors.textPrimary, fontSize: 14),
                  decoration: const InputDecoration(
                    labelText: 'Country / Region',
                    hintText: 'e.g. Egypt',
                    prefixIcon: Icon(Icons.public_rounded, size: 20),
                  ),
                  validator: (v) => v == null || v.trim().isEmpty
                      ? 'Enter your country'
                      : null,
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),

          // Equipment
          _buildSection(
            title: 'Equipment Available',
            icon: Icons.sports_gymnastics_rounded,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (_selectedEquipment.isEmpty)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Text(
                      'Select at least one option',
                      style: TextStyle(
                        color: AppColors.errorColor.withOpacity(0.8),
                        fontSize: 12,
                      ),
                    ),
                  ),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: _equipmentOptions.map((equip) {
                    final sel = _selectedEquipment.contains(equip);
                    return GestureDetector(
                      onTap: () => setState(() {
                        sel
                            ? _selectedEquipment.remove(equip)
                            : _selectedEquipment.add(equip);
                      }),
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 150),
                        padding: const EdgeInsets.symmetric(
                            horizontal: 12, vertical: 8),
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
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(
                            color: sel
                                ? AppColors.primary
                                : const Color(0xFF3A3A4E),
                          ),
                        ),
                        child: Text(
                          equip,
                          style: TextStyle(
                            color: sel
                                ? Colors.white
                                : AppColors.textMuted,
                            fontWeight: FontWeight.w600,
                            fontSize: 12,
                          ),
                        ),
                      ),
                    );
                  }).toList(),
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),

          // Schedule + Bias
          _buildSection(
            title: 'Schedule & Intensity',
            icon: Icons.calendar_month_rounded,
            child: Column(
              children: [
                _buildDropdown<int>(
                  label: 'Days Per Week',
                  value: _daysPerWeek,
                  items: [2, 3, 4, 5, 6],
                  display: (e) => '$e days',
                  onChanged: (v) => setState(() => _daysPerWeek = v),
                  validator: (v) => v == null ? 'Select days' : null,
                ),
                const SizedBox(height: 12),
                _buildDropdown<String>(
                  label: 'Session Duration',
                  value: _workoutDuration,
                  items: _workoutDurations,
                  display: (e) =>
                      '${e[0].toUpperCase()}${e.substring(1)}',
                  onChanged: (v) => setState(() => _workoutDuration = v),
                  validator: (v) =>
                      v == null ? 'Select duration' : null,
                ),
                const SizedBox(height: 12),
                _buildDropdown<String>(
                  label: 'Cardio / Strength Bias',
                  value: _cardioStrengthBias,
                  items: _cardioStrengthBiases,
                  display: (e) =>
                      '${e[0].toUpperCase()}${e.substring(1)}',
                  onChanged: (v) =>
                      setState(() => _cardioStrengthBias = v),
                  validator: (v) => v == null ? 'Select bias' : null,
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),

          if (_errorMessage != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Text(
                _errorMessage!,
                textAlign: TextAlign.center,
                style: const TextStyle(
                    color: AppColors.errorColor, fontSize: 13),
              ),
            ),

          // Generate button
          _isGenerating
              ? _buildLoadingButton('Generating your plan…')
              : _GradientButton(
                  label: 'Generate Workout Plan',
                  icon: Icons.fitness_center_rounded,
                  onTap: _generatePlan,
                ),
        ],
      ),
    );
  }

  Widget _buildUserInfoCard() {
    final user = _authService.currentUser;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.primary.withOpacity(0.08),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.primary.withOpacity(0.2)),
      ),
      child: Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                  colors: [AppColors.primary, AppColors.primaryLight]),
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.person_rounded,
                color: Colors.white, size: 22),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  user?.name ?? 'Athlete',
                  style: const TextStyle(
                    color: AppColors.textPrimary,
                    fontWeight: FontWeight.w700,
                    fontSize: 14,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  '${user?.goalType?.replaceAll('_', ' ') ?? 'Goal'} · '
                  '${user?.height?.round() ?? '?'} cm · '
                  '${user?.weight?.round() ?? '?'} kg',
                  style: const TextStyle(
                      color: AppColors.textMuted, fontSize: 12),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSection({
    required String title,
    required IconData icon,
    required Widget child,
  }) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppColors.cardBg,
        borderRadius: BorderRadius.circular(18),
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
          const SizedBox(height: 14),
          child,
        ],
      ),
    );
  }

  Widget _buildDropdown<T>({
    required String label,
    required T? value,
    required List<T> items,
    required String Function(T) display,
    required void Function(T?) onChanged,
    String? Function(T?)? validator,
  }) {
    return DropdownButtonFormField<T>(
      value: value,
      dropdownColor: AppColors.cardBg,
      style: const TextStyle(color: AppColors.textPrimary, fontSize: 14),
      decoration: InputDecoration(
        labelText: label,
        filled: true,
        fillColor: const Color(0xFF14141E),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Color(0xFF2E2E3E)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Color(0xFF2E2E3E)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide:
              const BorderSide(color: AppColors.primary, width: 1.5),
        ),
        labelStyle: const TextStyle(color: AppColors.textMuted, fontSize: 13),
      ),
      items: items
          .map((e) => DropdownMenuItem<T>(
                value: e,
                child: Text(display(e)),
              ))
          .toList(),
      onChanged: onChanged,
      validator: validator,
    );
  }

  // ── Result View ───────────────────────────────────────────────────────────

  Widget _buildResultView() {
    final plan = _generatedPlan!;
    return FadeTransition(
      opacity: _resultCtrl,
      child: Column(
        children: [
          // Plan header
          Container(
            margin: const EdgeInsets.fromLTRB(20, 8, 20, 0),
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF2A1A10), Color(0xFF1A0A03)],
              ),
              borderRadius: BorderRadius.circular(20),
              border:
                  Border.all(color: AppColors.primary.withOpacity(0.3)),
            ),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        plan.planName,
                        style: const TextStyle(
                          color: AppColors.textPrimary,
                          fontWeight: FontWeight.w800,
                          fontSize: 18,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Row(
                        children: [
                          _chip(
                            '${plan.daysPerWeek} days/wk',
                            AppColors.primary,
                          ),
                          const SizedBox(width: 8),
                          _chip(plan.fitnessLevel, AppColors.secondary),
                        ],
                      ),
                    ],
                  ),
                ),
                const Icon(Icons.fitness_center_rounded,
                    color: AppColors.primary, size: 36),
              ],
            ),
          ),
          const SizedBox(height: 4),

          Expanded(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 28),
              physics: const BouncingScrollPhysics(),
              children: [
                ...plan.schedule.map(_buildDayCard),
                const SizedBox(height: 16),
                OutlinedButton.icon(
                  onPressed: () => setState(() {
                    _generatedPlan = null;
                    _sessionId = null;
                  }),
                  icon: const Icon(Icons.refresh_rounded, size: 18),
                  label: const Text('Generate New Plan'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppColors.primary,
                    side: const BorderSide(color: AppColors.primary),
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(14)),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDayCard(WorkoutDay day) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: AppColors.cardBg,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: day.isRestDay
              ? const Color(0xFF2E2E3E)
              : AppColors.primary.withOpacity(0.25),
        ),
      ),
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
          leading: Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              gradient: day.isRestDay
                  ? null
                  : const LinearGradient(
                      colors: [AppColors.primary, AppColors.primaryLight],
                    ),
              color: day.isRestDay ? const Color(0xFF2A2A3E) : null,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Center(
              child: Text(
                'D${day.day}',
                style: TextStyle(
                  color:
                      day.isRestDay ? AppColors.textMuted : Colors.white,
                  fontWeight: FontWeight.w800,
                  fontSize: 12,
                ),
              ),
            ),
          ),
          title: Text(
            day.dayName,
            style: const TextStyle(
              color: AppColors.textPrimary,
              fontWeight: FontWeight.w700,
              fontSize: 14,
            ),
          ),
          subtitle: Text(
            day.isRestDay ? 'Recovery day' : day.focus ?? '',
            style: TextStyle(
              color: day.isRestDay
                  ? AppColors.textMuted
                  : AppColors.primary,
              fontSize: 12,
            ),
          ),
          children: day.isRestDay
              ? [
                  Padding(
                    padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                    child: Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: AppColors.secondary.withOpacity(0.08),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: const Row(
                        children: [
                          Icon(Icons.self_improvement_rounded,
                              color: AppColors.secondary, size: 18),
                          SizedBox(width: 8),
                          Text(
                            'Rest, stretch, and recover.',
                            style: TextStyle(
                                color: AppColors.textMuted, fontSize: 13),
                          ),
                        ],
                      ),
                    ),
                  ),
                ]
              : day.exercises.map(_buildExerciseTile).toList(),
        ),
      ),
    );
  }

  Widget _buildExerciseTile(ExerciseItem ex) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: const Color(0xFF14141E),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: const Color(0xFF2E2E3E)),
        ),
        child: Row(
          children: [
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                color: AppColors.primary.withOpacity(0.12),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.sports_gymnastics_rounded,
                  color: AppColors.primary, size: 18),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    ex.name,
                    style: const TextStyle(
                      color: AppColors.textPrimary,
                      fontWeight: FontWeight.w700,
                      fontSize: 13,
                    ),
                  ),
                  const SizedBox(height: 3),
                  Text(
                    '${ex.bodyPart ?? ''}  ·  ${ex.equipment ?? ''}',
                    style: const TextStyle(
                        color: AppColors.textMuted, fontSize: 11),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _chip(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        label,
        style: TextStyle(
            color: color, fontSize: 11, fontWeight: FontWeight.w600),
      ),
    );
  }
}

// ── Gradient CTA button ───────────────────────────────────────────────────────

class _GradientButton extends StatelessWidget {
  final String label;
  final IconData? icon;
  final VoidCallback onTap;

  const _GradientButton({
    required this.label,
    required this.onTap,
    this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: double.infinity,
        height: 54,
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [AppColors.primary, AppColors.primaryLight],
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
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (icon != null) ...[
              Icon(icon, color: Colors.white, size: 20),
              const SizedBox(width: 8),
            ],
            Text(
              label,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 16,
                fontWeight: FontWeight.w700,
                letterSpacing: 0.5,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

Widget _buildLoadingButton(String label) {
  return Container(
    width: double.infinity,
    height: 54,
    decoration: BoxDecoration(
      gradient: const LinearGradient(
        colors: [AppColors.primary, AppColors.primaryLight],
      ),
      borderRadius: BorderRadius.circular(14),
    ),
    child: Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const SizedBox(
          width: 20,
          height: 20,
          child: CircularProgressIndicator(
            strokeWidth: 2.5,
            valueColor: AlwaysStoppedAnimation(Colors.white),
          ),
        ),
        const SizedBox(width: 12),
        Text(
          label,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 15,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    ),
  );
}
