// lib/screens/diet_plan_screen.dart
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:gym2/colors/colors.dart';
import 'package:gym2/services/auth_service.dart';
import 'package:gym2/services/location_service.dart';
import 'package:gym2/services/recommendation_service.dart';
import 'package:gym2/models/diet_plan_model.dart';
import 'package:gym2/constants/app_constants.dart';
import 'package:gym2/models/user_model.dart';

class DietPlanScreen extends StatefulWidget {
  const DietPlanScreen({super.key});

  @override
  State<DietPlanScreen> createState() => _DietPlanScreenState();
}

class _DietPlanScreenState extends State<DietPlanScreen>
    with TickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();
  final AuthService _authService = AuthService();
  final RecommendationService _recommendationService = RecommendationService();

  // Form state
  int? _mealsPerDay;
  String? _dietType;
  final _allergiesController = TextEditingController();
  final _intolerancesController = TextEditingController();
  String? _cookingTime;
  String? _proteinFocus;
  String? _detectedCountry;
  String? _manualCountry;
  bool _isLocating = false;
  bool _useManualLocation = false;

  bool _isGenerating = false;
  DietPlanModel? _generatedPlan;
  String? _errorMessage;
  String? _sessionId;

  late final AnimationController _resultCtrl;

  @override
  void initState() {
    super.initState();
    _resultCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 500),
    );
    _detectLocation();
    _prefillDietType();
  }

  @override
  void dispose() {
    _resultCtrl.dispose();
    _allergiesController.dispose();
    _intolerancesController.dispose();
    super.dispose();
  }

  void _prefillDietType() {
    final user = _authService.currentUser;
    if (user?.isVegetarian == true) _dietType = 'vegetarian';
  }

  Future<void> _detectLocation() async {
    setState(() => _isLocating = true);
    final country = await LocationService.detectCountry();
    setState(() {
      _detectedCountry = country;
      _isLocating = false;
      if (country == null) _useManualLocation = true;
    });
  }

  String? get _derivedCuisine {
    final c = _useManualLocation ? _manualCountry : _detectedCountry;
    return c != null ? AppConstants.locationToCuisine[c] : null;
  }

  // ── API ──────────────────────────────────────────────────────────────────

  Future<void> _generatePlan() async {
    if (!_formKey.currentState!.validate()) return;

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

      final apiResponse = await _recommendationService.generateMealPlan(
        _sessionId!,
        topK: 5,
        numFetch: 20,
      );

      if (!mounted) return;
      final plan = _mapToPlan(apiResponse, user);
      setState(() {
        _generatedPlan = plan;
        _isGenerating = false;
      });
      _resultCtrl.forward(from: 0);
    } on DioException catch (e) {
      if (!mounted) return;
      // Extract the human-readable detail from the server 422/404 response
      String msg;
      try {
        final data = e.response?.data;
        if (data is Map && data['detail'] != null) {
          msg = data['detail'].toString();
        } else {
          msg = e.message ?? 'Unknown error';
        }
      } catch (_) {
        msg = e.message ?? 'Unknown error';
      }
      // Reset session so next attempt creates a fresh one
      _sessionId = null;
      setState(() {
        _errorMessage = '⚠️ $msg';
        _isGenerating = false;
      });
    } catch (e) {
      if (!mounted) return;
      // Reset session on any other error too
      _sessionId = null;
      setState(() {
        _errorMessage = 'Failed: ${e.toString()}';
        _isGenerating = false;
      });
    }
  }

  // Valid API values — must match backend constants.py exactly
  String _sanitizeSex(String gender) {
    final g = gender.toLowerCase();
    if (g == 'male' || g == 'female') return g;
    return 'male'; // fallback for 'other' — API only accepts male/female
  }

  String _sanitizeGoalType(String? goalType) {
    const valid = {'fat_loss', 'muscle_gain', 'maintenance', 'endurance'};
    if (valid.contains(goalType)) return goalType!;
    // Map screen display values to API values
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
        'fitness_level': 'beginner',
        'activity_level': 'light',
        'workout_location': 'both',
        'available_equipment': <String>[],
        'diet_type': _dietType ?? user.defaultDietType,
        'allergies': _allergiesController.text
            .split(',')
            .map((e) => e.trim())
            .where((e) => e.isNotEmpty)
            .toList(),
        'intolerances': _intolerancesController.text
            .split(',')
            .map((e) => e.trim())
            .where((e) => e.isNotEmpty)
            .toList(),
        'country': _useManualLocation ? _manualCountry : _detectedCountry,
        'preferred_workout_duration': 'medium',
        'cardio_strength_bias': 'balanced',
        'meals_per_day': _mealsPerDay ?? 3,
        'cooking_time_preference': _cookingTime ?? 'flexible',
        'protein_focus': _proteinFocus ?? 'medium',
      };

  DietPlanModel _mapToPlan(Map<String, dynamic> data, UserModel user) {
    // daily_macros is a MacroTargetsResponse object
    final dailyMacros = data['daily_macros'] as Map<String, dynamic>;
    final macros = MacroBreakdown(
      proteinG: (dailyMacros['protein_g'] as num).toDouble(),
      carbsG: (dailyMacros['carbs_g'] as num).toDouble(),
      fatG: (dailyMacros['fat_g'] as num).toDouble(),
    );

    final totalCalories = (data['target_calories'] as num).round();
    final slots = data['slots'] as List;
    final meals = <MealItem>[];

    for (final slot in slots) {
      final slotMap = slot as Map<String, dynamic>;
      final slotName = slotMap['slot'] as String;
      final recipes = slotMap['recipes'] as List;
      for (final r in recipes) {
        final recipe = r as Map<String, dynamic>;
        meals.add(MealItem(
          mealType: slotName,
          // API uses 'title' not 'name'
          name: (recipe['title'] ?? recipe['name'] ?? 'Meal') as String,
          calories: ((recipe['calories'] ?? 0) as num).round(),
          proteinG: ((recipe['protein_g'] ?? 0) as num).toDouble(),
          carbsG: ((recipe['carbs_g'] ?? 0) as num).toDouble(),
          fatG: ((recipe['fat_g'] ?? 0) as num).toDouble(),
          ingredients: [],
          recipe: null,
        ));
      }
    }

    final summary = data['summary'] as String? ?? '';

    return DietPlanModel(
      planName: 'Daily Meal Plan',
      totalCalories: totalCalories,
      macros: macros,
      days: [DayPlan(day: 1, dayName: 'Today', meals: meals)],
      notes: summary.isNotEmpty ? [summary] : [],
    );
  }

  void _showError(String msg) {
    setState(() => _errorMessage = msg);
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
                  'Diet Plan',
                  style: TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                Text(
                  'Personalized nutrition powered by AI',
                  style: TextStyle(color: AppColors.textMuted, fontSize: 12),
                ),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: AppColors.successColor.withOpacity(0.15),
              borderRadius: BorderRadius.circular(10),
              border:
                  Border.all(color: AppColors.successColor.withOpacity(0.3)),
            ),
            child: const Icon(Icons.restaurant_rounded,
                color: AppColors.successColor, size: 18),
          ),
        ],
      ),
    );
  }

  // ── Form View ─────────────────────────────────────────────────────────────

  Widget _buildFormView() {
    final user = _authService.currentUser;
    return Form(
      key: _formKey,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
        physics: const BouncingScrollPhysics(),
        children: [
          // User info card
          _buildUserInfoCard(user),
          const SizedBox(height: 16),

          // Meal preferences
          _buildSection(
            title: 'Meal Preferences',
            icon: Icons.set_meal_rounded,
            child: Column(
              children: [
                _buildDropdown<int>(
                  label: 'Meals per day',
                  value: _mealsPerDay,
                  items: AppConstants.mealCounts,
                  display: (e) => '$e meals',
                  onChanged: (v) => setState(() => _mealsPerDay = v),
                  validator: (v) => v == null ? 'Select meals per day' : null,
                ),
                const SizedBox(height: 12),
                _buildDropdown<String>(
                  label: 'Diet type',
                  value: _dietType,
                  items: AppConstants.dietTypes,
                  display: (e) =>
                      '${e[0].toUpperCase()}${e.substring(1)}',
                  onChanged: (v) => setState(() => _dietType = v),
                  validator: (v) => v == null ? 'Select diet type' : null,
                ),
                const SizedBox(height: 12),
                _buildDropdown<String>(
                  label: 'Cooking time preference',
                  value: _cookingTime,
                  items: AppConstants.cookingTimePreferences,
                  display: (e) =>
                      e == 'quick' ? 'Quick (< 30 min)' : 'Flexible',
                  onChanged: (v) => setState(() => _cookingTime = v),
                  validator: (v) =>
                      v == null ? 'Select cooking time' : null,
                ),
                const SizedBox(height: 12),
                _buildDropdown<String>(
                  label: 'Protein focus',
                  value: _proteinFocus,
                  items: AppConstants.proteinFocusLevels,
                  display: (e) =>
                      '${e[0].toUpperCase()}${e.substring(1)}',
                  onChanged: (v) => setState(() => _proteinFocus = v),
                  validator: (v) =>
                      v == null ? 'Select protein focus' : null,
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),

          // Dietary restrictions
          _buildSection(
            title: 'Dietary Restrictions',
            icon: Icons.no_food_rounded,
            child: Column(
              children: [
                _fieldRaw(
                  controller: _allergiesController,
                  label: 'Allergies',
                  hint: 'e.g. nuts, dairy, gluten',
                  icon: Icons.warning_amber_rounded,
                ),
                const SizedBox(height: 12),
                _fieldRaw(
                  controller: _intolerancesController,
                  label: 'Intolerances',
                  hint: 'e.g. lactose, fructose',
                  icon: Icons.no_meals_rounded,
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),

          // Location
          _buildSection(
            title: 'Location & Cuisine',
            icon: Icons.location_on_outlined,
            child: _buildLocationContent(),
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

          _isGenerating
              ? _buildLoadingBtn('Creating your meal plan…')
              : _GradientButton(
                  label: 'Generate Diet Plan',
                  icon: Icons.restaurant_rounded,
                  onTap: _generatePlan,
                ),
        ],
      ),
    );
  }

  Widget _buildUserInfoCard(UserModel? user) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.successColor.withOpacity(0.08),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.successColor.withOpacity(0.2)),
      ),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: AppColors.successColor.withOpacity(0.15),
              shape: BoxShape.circle,
            ),
            child: const Icon(Icons.person_rounded,
                color: AppColors.successColor, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  user?.name ?? 'Athlete',
                  style: const TextStyle(
                    color: AppColors.textPrimary,
                    fontWeight: FontWeight.w700,
                    fontSize: 13,
                  ),
                ),
                Text(
                  'Goal: ${user?.goalType?.replaceAll('_', ' ') ?? '—'}  ·  '
                  'Diet: ${user?.defaultDietType ?? '—'}',
                  style: const TextStyle(
                      color: AppColors.textMuted, fontSize: 11),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLocationContent() {
    if (_isLocating) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(12),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  valueColor: AlwaysStoppedAnimation(AppColors.primary),
                ),
              ),
              SizedBox(width: 10),
              Text(
                'Detecting your location…',
                style: TextStyle(color: AppColors.textMuted, fontSize: 13),
              ),
            ],
          ),
        ),
      );
    }

    if (!_useManualLocation && _detectedCountry != null) {
      return Column(
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppColors.successColor.withOpacity(0.08),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                  color: AppColors.successColor.withOpacity(0.25)),
            ),
            child: Row(
              children: [
                const Icon(Icons.gps_fixed_rounded,
                    color: AppColors.successColor, size: 18),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _detectedCountry!,
                        style: const TextStyle(
                          color: AppColors.textPrimary,
                          fontWeight: FontWeight.w700,
                          fontSize: 13,
                        ),
                      ),
                      if (_derivedCuisine != null)
                        Text(
                          'Cuisine: ${_derivedCuisine!}',
                          style: const TextStyle(
                              color: AppColors.textMuted, fontSize: 11),
                        ),
                    ],
                  ),
                ),
                GestureDetector(
                  onTap: () =>
                      setState(() => _useManualLocation = true),
                  child: Container(
                    padding: const EdgeInsets.all(6),
                    decoration: BoxDecoration(
                      color: AppColors.cardBg,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(Icons.edit_rounded,
                        size: 16, color: AppColors.textMuted),
                  ),
                ),
              ],
            ),
          ),
        ],
      );
    }

    return Column(
      children: [
        TextFormField(
          style: const TextStyle(color: AppColors.textPrimary, fontSize: 14),
          decoration: const InputDecoration(
            labelText: 'Your country',
            hintText: 'e.g. Egypt, Italy, USA',
            prefixIcon: Icon(Icons.public_rounded, size: 20),
          ),
          onChanged: (v) => setState(() => _manualCountry = v),
          validator: (v) {
            if (_useManualLocation && (v == null || v.isEmpty)) {
              return 'Please enter your country';
            }
            return null;
          },
        ),
        if (_manualCountry != null && _derivedCuisine != null) ...[
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerLeft,
            child: Text(
              'Cuisine: $_derivedCuisine',
              style: const TextStyle(
                  color: AppColors.secondary, fontSize: 12),
            ),
          ),
        ],
        TextButton.icon(
          onPressed: () {
            setState(() {
              _useManualLocation = false;
              _manualCountry = null;
              _detectLocation();
            });
          },
          icon: const Icon(Icons.gps_not_fixed_rounded, size: 16),
          label: const Text('Retry GPS detection'),
          style: TextButton.styleFrom(foregroundColor: AppColors.primary),
        ),
      ],
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
              Icon(icon, color: AppColors.successColor, size: 18),
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
          borderSide: const BorderSide(color: AppColors.primary, width: 1.5),
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

  Widget _fieldRaw({
    required TextEditingController controller,
    required String label,
    required String hint,
    required IconData icon,
  }) {
    return TextFormField(
      controller: controller,
      style: const TextStyle(color: AppColors.textPrimary, fontSize: 14),
      decoration: InputDecoration(
        labelText: label,
        hintText: hint,
        prefixIcon: Icon(icon, size: 20),
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
          borderSide: const BorderSide(color: AppColors.primary, width: 1.5),
        ),
        labelStyle: const TextStyle(color: AppColors.textMuted, fontSize: 13),
        hintStyle: const TextStyle(color: AppColors.textDisabled, fontSize: 13),
      ),
    );
  }

  // ── Result View ───────────────────────────────────────────────────────────

  Widget _buildResultView() {
    final plan = _generatedPlan!;
    return FadeTransition(
      opacity: _resultCtrl,
      child: Column(
        children: [
          // Header
          Container(
            margin: const EdgeInsets.fromLTRB(20, 8, 20, 0),
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF0D2A1A), Color(0xFF061A10)],
              ),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(
                  color: AppColors.successColor.withOpacity(0.3)),
            ),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Daily Meal Plan',
                        style: TextStyle(
                          color: AppColors.textPrimary,
                          fontWeight: FontWeight.w800,
                          fontSize: 18,
                        ),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        '${plan.totalCalories} kcal / day',
                        style: const TextStyle(
                          color: AppColors.successColor,
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                ),
                const Icon(Icons.restaurant_rounded,
                    color: AppColors.successColor, size: 36),
              ],
            ),
          ),

          // Macro row
          _buildMacroRow(plan.macros),

          Expanded(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 28),
              physics: const BouncingScrollPhysics(),
              children: [
                ...plan.days.map(_buildDayCard),
                if (plan.notes != null && plan.notes!.isNotEmpty)
                  _buildNotesCard(plan.notes!),
                const SizedBox(height: 12),
                OutlinedButton.icon(
                  onPressed: () => setState(() {
                    _generatedPlan = null;
                    _sessionId = null;
                  }),
                  icon: const Icon(Icons.refresh_rounded, size: 18),
                  label: const Text('Generate New Plan'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppColors.successColor,
                    side: const BorderSide(color: AppColors.successColor),
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

  Widget _buildMacroRow(MacroBreakdown macros) {
    return Container(
      margin: const EdgeInsets.fromLTRB(20, 10, 20, 0),
      padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 20),
      decoration: BoxDecoration(
        color: AppColors.cardBg,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF2E2E3E)),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceAround,
        children: [
          _macroItem('Protein', '${macros.proteinG.toInt()}g',
              const Color(0xFFEF5350)),
          _vertDivider(),
          _macroItem(
              'Carbs', '${macros.carbsG.toInt()}g', AppColors.warningColor),
          _vertDivider(),
          _macroItem(
              'Fat', '${macros.fatG.toInt()}g', AppColors.secondary),
        ],
      ),
    );
  }

  Widget _macroItem(String label, String value, Color color) {
    return Column(
      children: [
        Text(
          value,
          style: TextStyle(
            color: color,
            fontWeight: FontWeight.w800,
            fontSize: 20,
          ),
        ),
        const SizedBox(height: 2),
        Text(
          label,
          style: const TextStyle(color: AppColors.textMuted, fontSize: 11),
        ),
      ],
    );
  }

  Widget _vertDivider() {
    return Container(
      width: 1,
      height: 36,
      color: const Color(0xFF2E2E3E),
    );
  }

  Widget _buildDayCard(DayPlan day) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: AppColors.cardBg,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0xFF2E2E3E)),
      ),
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          initiallyExpanded: true,
          tilePadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 6),
          leading: Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: AppColors.successColor.withOpacity(0.15),
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Icon(Icons.today_rounded,
                color: AppColors.successColor, size: 20),
          ),
          title: Text(
            day.dayName ?? 'Day ${day.day}',
            style: const TextStyle(
              color: AppColors.textPrimary,
              fontWeight: FontWeight.w700,
              fontSize: 14,
            ),
          ),
          subtitle: Text(
            '${day.meals.length} meals',
            style: const TextStyle(
                color: AppColors.successColor, fontSize: 12),
          ),
          children: day.meals.map(_buildMealCard).toList(),
        ),
      ),
    );
  }

  Widget _buildMealCard(MealItem meal) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(14, 0, 14, 14),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: const Color(0xFF14141E),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: const Color(0xFF2E2E3E)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 10, vertical: 3),
                  decoration: BoxDecoration(
                    color: _mealTypeColor(meal.mealType).withOpacity(0.15),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    '${meal.mealType[0].toUpperCase()}${meal.mealType.substring(1)}',
                    style: TextStyle(
                      color: _mealTypeColor(meal.mealType),
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
                const Spacer(),
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: AppColors.primary.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    '${meal.calories} kcal',
                    style: const TextStyle(
                      color: AppColors.primary,
                      fontWeight: FontWeight.w700,
                      fontSize: 12,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              meal.name,
              style: const TextStyle(
                color: AppColors.textPrimary,
                fontWeight: FontWeight.w700,
                fontSize: 14,
              ),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                _miniMacro('P ${meal.proteinG.toInt()}g',
                    const Color(0xFFEF5350)),
                const SizedBox(width: 8),
                _miniMacro(
                    'C ${meal.carbsG.toInt()}g', AppColors.warningColor),
                const SizedBox(width: 8),
                _miniMacro('F ${meal.fatG.toInt()}g', AppColors.secondary),
              ],
            ),
            // Feedback buttons
            const SizedBox(height: 10),
            Row(
              children: [
                _feedbackBtn(Icons.thumb_up_rounded, true, meal),
                const SizedBox(width: 8),
                _feedbackBtn(Icons.thumb_down_rounded, false, meal),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _feedbackBtn(IconData icon, bool liked, MealItem meal) {
    return GestureDetector(
      onTap: () {
        // meal.id unavailable from model, so we skip feedback for now
        // TODO: pass recipe_id when model is extended
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: AppColors.cardBg,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: const Color(0xFF2E2E3E)),
        ),
        child: Icon(
          icon,
          size: 16,
          color: liked ? AppColors.successColor : AppColors.textDisabled,
        ),
      ),
    );
  }

  Color _mealTypeColor(String type) {
    switch (type.toLowerCase()) {
      case 'breakfast':
        return AppColors.warningColor;
      case 'lunch':
        return AppColors.primary;
      case 'dinner':
        return AppColors.accent3;
      default:
        return AppColors.secondary;
    }
  }

  Widget _miniMacro(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        text,
        style: TextStyle(
          color: color,
          fontSize: 11,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  Widget _buildNotesCard(List<String> notes) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.secondary.withOpacity(0.08),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.secondary.withOpacity(0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.info_outline_rounded,
                  color: AppColors.secondary, size: 16),
              SizedBox(width: 6),
              Text(
                'Plan Summary',
                style: TextStyle(
                  color: AppColors.secondary,
                  fontWeight: FontWeight.w700,
                  fontSize: 13,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ...notes.map(
            (n) => Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Text(
                '· $n',
                style: const TextStyle(
                    color: AppColors.textMuted, fontSize: 12, height: 1.4),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ── Gradient button ───────────────────────────────────────────────────────────

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

Widget _buildLoadingBtn(String label) {
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