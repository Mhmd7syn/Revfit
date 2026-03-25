// lib/screens/home_screen.dart
import 'package:flutter/material.dart';
import 'package:gym2/colors/colors.dart';
import 'package:gym2/services/auth_service.dart';
import 'Chat_bot_screen.dart';
import 'workout_plan_screen.dart';
import 'diet_plan_screen.dart';
import 'pose_analysis_screen.dart';
import 'login_screen.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final user = AuthService().currentUser;
    final firstName = (user?.name ?? 'Athlete').split(' ').first;
    final bmi = user?.bmi;
    final goalType = (user?.goalType ?? 'maintenance')
        .replaceAll('_', ' ')
        .split(' ')
        .map((w) => '${w[0].toUpperCase()}${w.substring(1)}')
        .join(' ');

    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: AppColors.heroGradient),
        child: SafeArea(
          child: CustomScrollView(
            physics: const BouncingScrollPhysics(),
            slivers: [
              SliverToBoxAdapter(child: _buildTopBar(context, firstName)),
              SliverToBoxAdapter(child: _buildGreetingHero(context, firstName, goalType, bmi)),
              SliverToBoxAdapter(child: _buildSectionLabel('Quick Actions')),
              SliverToBoxAdapter(child: _buildActionCards(context)),
              SliverToBoxAdapter(child: _buildSectionLabel('Your Stats')),
              SliverToBoxAdapter(child: _buildStatsRow(user)),
              SliverToBoxAdapter(child: _buildTip()),
              const SliverToBoxAdapter(child: SizedBox(height: 32)),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTopBar(BuildContext context, String firstName) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 16, 24, 0),
      child: Row(
        children: [
          // Avatar circle
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [AppColors.primary, AppColors.primaryLight],
              ),
              shape: BoxShape.circle,
            ),
            child: Center(
              child: Text(
                firstName.isNotEmpty ? firstName[0].toUpperCase() : 'A',
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w800,
                  fontSize: 18,
                ),
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Hello, $firstName 👋',
                  style: const TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const Text(
                  'Ready to crush today?',
                  style: TextStyle(color: AppColors.textMuted, fontSize: 12),
                ),
              ],
            ),
          ),
          // Sign out button
          GestureDetector(
            onTap: () async {
              await AuthService().signOut();
              if (context.mounted) {
                Navigator.pushReplacement(
                  context,
                  MaterialPageRoute(builder: (_) => const LoginScreen()),
                );
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
              child: const Icon(
                Icons.logout_rounded,
                size: 18,
                color: AppColors.textMuted,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildGreetingHero(
    BuildContext context,
    String firstName,
    String goalType,
    double? bmi,
  ) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 24, 24, 0),
      child: Container(
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [Color(0xFF2A1A10), Color(0xFF1A0A03)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(24),
          border: Border.all(color: AppColors.primary.withOpacity(0.3)),
          boxShadow: [
            BoxShadow(
              color: AppColors.primary.withOpacity(0.15),
              blurRadius: 24,
              offset: const Offset(0, 8),
            ),
          ],
        ),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: AppColors.primary.withOpacity(0.2),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      goalType,
                      style: const TextStyle(
                        color: AppColors.primary,
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        letterSpacing: 0.5,
                      ),
                    ),
                  ),
                  const SizedBox(height: 10),
                  const Text(
                    "Let's build a\nbetter you today!",
                    style: TextStyle(
                      color: AppColors.textPrimary,
                      fontSize: 20,
                      fontWeight: FontWeight.w800,
                      height: 1.3,
                    ),
                  ),
                  if (bmi != null) ...[
                    const SizedBox(height: 10),
                    Text(
                      'BMI: $bmi',
                      style: const TextStyle(
                        color: AppColors.textMuted,
                        fontSize: 13,
                      ),
                    ),
                  ],
                ],
              ),
            ),
            Container(
              width: 80,
              height: 80,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [AppColors.primary, AppColors.primaryLight],
                ),
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: AppColors.primary.withOpacity(0.4),
                    blurRadius: 20,
                    spreadRadius: 4,
                  ),
                ],
              ),
              child: const Icon(
                Icons.fitness_center_rounded,
                color: Colors.white,
                size: 38,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSectionLabel(String label) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 28, 24, 12),
      child: Text(
        label,
        style: const TextStyle(
          color: AppColors.textPrimary,
          fontSize: 18,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }

  Widget _buildActionCards(BuildContext context) {
    final cards = [
      _ActionCard(
        icon: Icons.smart_toy_rounded,
        label: 'AI Chat',
        sublabel: 'Ask anything fitness',
        gradient: const LinearGradient(
          colors: [Color(0xFF1A2A4A), Color(0xFF0D1A30)],
        ),
        accentColor: AppColors.secondary,
        onTap: () => Navigator.push(
          context,
          _route(const ChatScreen()),
        ),
      ),
      _ActionCard(
        icon: Icons.fitness_center_rounded,
        label: 'Workout Plan',
        sublabel: 'AI-generated program',
        gradient: const LinearGradient(
          colors: [Color(0xFF2A1A10), Color(0xFF1A0A03)],
        ),
        accentColor: AppColors.primary,
        onTap: () => Navigator.push(
          context,
          _route(const WorkoutPlanScreen()),
        ),
      ),
      _ActionCard(
        icon: Icons.sports_gymnastics_rounded,
        label: 'Form Checker',
        sublabel: 'AI pose analysis',
        gradient: const LinearGradient(
          colors: [Color(0xFF1A1A2A), Color(0xFF0D0D1A)],
        ),
        accentColor: AppColors.accent3,
        onTap: () => Navigator.push(
          context,
          _route(const PoseAnalysisScreen()),
        ),
      ),
      _ActionCard(
        icon: Icons.restaurant_rounded,
        label: 'Diet Plan',
        sublabel: 'Personalized nutrition',
        gradient: const LinearGradient(
          colors: [Color(0xFF1A2A1A), Color(0xFF0D1A0D)],
        ),
        accentColor: AppColors.successColor,
        onTap: () => Navigator.push(
          context,
          _route(const DietPlanScreen()),
        ),
      ),
    ];

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Column(
        children: cards
            .map(
              (c) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: c,
              ),
            )
            .toList(),
      ),
    );
  }

  Widget _buildStatsRow(user) {
    final stats = [
      _Stat(
        label: 'Height',
        value: user?.height != null ? '${user!.height.round()} cm' : '—',
        icon: Icons.height_rounded,
        color: AppColors.secondary,
      ),
      _Stat(
        label: 'Weight',
        value: user?.weight != null ? '${user!.weight.round()} kg' : '—',
        icon: Icons.monitor_weight_outlined,
        color: AppColors.primary,
      ),
      _Stat(
        label: 'Age',
        value: user?.age != null ? '${user!.age} yrs' : '—',
        icon: Icons.cake_outlined,
        color: AppColors.accent3,
      ),
    ];

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Row(
        children: stats
            .map(
              (s) => Expanded(
                child: Padding(
                  padding:
                      EdgeInsets.only(right: stats.indexOf(s) < 2 ? 10 : 0),
                  child: _buildStatChip(s),
                ),
              ),
            )
            .toList(),
      ),
    );
  }

  Widget _buildStatChip(_Stat stat) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 12),
      decoration: BoxDecoration(
        color: AppColors.cardBg,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF2E2E3E)),
      ),
      child: Column(
        children: [
          Icon(stat.icon, color: stat.color, size: 22),
          const SizedBox(height: 8),
          Text(
            stat.value,
            style: const TextStyle(
              color: AppColors.textPrimary,
              fontWeight: FontWeight.w700,
              fontSize: 15,
            ),
          ),
          const SizedBox(height: 2),
          Text(
            stat.label,
            style: const TextStyle(color: AppColors.textMuted, fontSize: 11),
          ),
        ],
      ),
    );
  }

  Widget _buildTip() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(24, 20, 24, 0),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.secondary.withOpacity(0.08),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.secondary.withOpacity(0.2)),
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AppColors.secondary.withOpacity(0.15),
                borderRadius: BorderRadius.circular(10),
              ),
              child: const Icon(
                Icons.tips_and_updates_rounded,
                color: AppColors.secondary,
                size: 20,
              ),
            ),
            const SizedBox(width: 12),
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Pro Tip',
                    style: TextStyle(
                      color: AppColors.secondary,
                      fontWeight: FontWeight.w700,
                      fontSize: 13,
                    ),
                  ),
                  SizedBox(height: 2),
                  Text(
                    'Chat with the AI assistant for instant workout advice!',
                    style: TextStyle(
                      color: AppColors.textMuted,
                      fontSize: 12,
                      height: 1.4,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  PageRouteBuilder _route(Widget screen) {
    return PageRouteBuilder(
      pageBuilder: (_, a, __) => screen,
      transitionsBuilder: (_, a, __, child) => FadeTransition(
        opacity: a,
        child: child,
      ),
      transitionDuration: const Duration(milliseconds: 250),
    );
  }
}

class _Stat {
  final String label;
  final String value;
  final IconData icon;
  final Color color;

  const _Stat({
    required this.label,
    required this.value,
    required this.icon,
    required this.color,
  });
}

class _ActionCard extends StatefulWidget {
  final IconData icon;
  final String label;
  final String sublabel;
  final LinearGradient gradient;
  final Color accentColor;
  final VoidCallback onTap;

  const _ActionCard({
    required this.icon,
    required this.label,
    required this.sublabel,
    required this.gradient,
    required this.accentColor,
    required this.onTap,
  });

  @override
  State<_ActionCard> createState() => _ActionCardState();
}

class _ActionCardState extends State<_ActionCard>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _scale;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 100),
      lowerBound: 0.95,
      upperBound: 1.0,
      value: 1.0,
    );
    _scale = _ctrl;
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ScaleTransition(
      scale: _scale,
      child: GestureDetector(
        onTapDown: (_) => _ctrl.reverse(),
        onTapUp: (_) {
          _ctrl.forward();
          widget.onTap();
        },
        onTapCancel: () => _ctrl.forward(),
        child: Container(
          height: 80,
          padding: const EdgeInsets.symmetric(horizontal: 20),
          decoration: BoxDecoration(
            gradient: widget.gradient,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: widget.accentColor.withOpacity(0.25)),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.3),
                blurRadius: 12,
                offset: const Offset(0, 4),
              ),
            ],
          ),
          child: Row(
            children: [
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: widget.accentColor.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(
                  widget.icon,
                  color: widget.accentColor,
                  size: 24,
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      widget.label,
                      style: const TextStyle(
                        color: AppColors.textPrimary,
                        fontWeight: FontWeight.w700,
                        fontSize: 15,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      widget.sublabel,
                      style: const TextStyle(
                        color: AppColors.textMuted,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
              Icon(
                Icons.arrow_forward_ios_rounded,
                color: widget.accentColor,
                size: 16,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
