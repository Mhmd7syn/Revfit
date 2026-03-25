import 'package:firebase_auth/firebase_auth.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import '../models/user_model.dart';

class AuthService {
  // ------------------------------------------------------------------
  // Singleton setup
  // ------------------------------------------------------------------

  AuthService._internal();

  static final AuthService _instance = AuthService._internal();

  factory AuthService() {
    return _instance;
  }

  // ------------------------------------------------------------------
  // Firebase instances
  // ------------------------------------------------------------------

  final FirebaseAuth _auth = FirebaseAuth.instance;
  final FirebaseFirestore _firestore = FirebaseFirestore.instance;

  // Store current user data
  UserModel? _currentUser;

  // Getter
  UserModel? get currentUser => _currentUser;

  // ------------------------------------------------------------------
  // Initialization
  // ------------------------------------------------------------------

  /// Load logged-in user when app starts
  Future<void> init() async {
    final user = _auth.currentUser;
    if (user != null) {
      await _loadUserData(user.uid);
    }
  }

  /// Load Firestore user document
  Future<UserModel?> _loadUserData(String uid) async {
    try {
      final doc = await _firestore.collection('users').doc(uid).get();

      if (doc.exists) {
        _currentUser = UserModel.fromMap(doc.data()!);
        return _currentUser;
      }
    } catch (e) {
      print("Error loading user data: $e");
    }

    return null;
  }

  // ------------------------------------------------------------------
  // Sign Up
  // ------------------------------------------------------------------

  Future<String?> signUpWithEmail({
    required String email,
    required String password,
    required UserModel userModel,
  }) async {
    try {
      // Create Firebase user
      UserCredential result = await _auth.createUserWithEmailAndPassword(
        email: email,
        password: password,
      );

      User? user = result.user;

      if (user == null) {
        throw Exception("User creation failed");
      }

      // Send email verification
      await user.sendEmailVerification();

      // Save user profile to Firestore
      await _firestore.collection("users").doc(user.uid).set({
        ...userModel.toMap(),
        "uid": user.uid,
        "createdAt": FieldValue.serverTimestamp(),
        "emailVerified": false,
      });

      // Load user into memory
      await _loadUserData(user.uid);

      return null;
    } on FirebaseAuthException catch (e) {
      return e.message;
    } catch (e) {
      return e.toString();
    }
  }

  // ------------------------------------------------------------------
  // Sign In
  // ------------------------------------------------------------------

  Future<String?> signInWithEmail({
    required String email,
    required String password,
  }) async {
    try {
      UserCredential result = await _auth.signInWithEmailAndPassword(
        email: email,
        password: password,
      );

      User? user = result.user;

      if (user == null) {
        throw Exception("Sign in failed");
      }

      // Load user data
      await _loadUserData(user.uid);

      return null;
    } on FirebaseAuthException catch (e) {
      return e.message;
    } catch (e) {
      return e.toString();
    }
  }

  // ------------------------------------------------------------------
  // Sign Out
  // ------------------------------------------------------------------

  Future<void> signOut() async {
    await _auth.signOut();
    _currentUser = null;
  }

  // ------------------------------------------------------------------
  // Refresh User
  // ------------------------------------------------------------------

  Future<void> refreshCurrentUser() async {
    final user = _auth.currentUser;

    if (user != null) {
      await _loadUserData(user.uid);
    }
  }
}
