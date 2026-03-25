// lib/services/location_service.dart
import 'package:geolocator/geolocator.dart';
import 'package:geocoding/geocoding.dart';

class LocationService {
  /// Request location permission and get current position.
  /// Returns [Position] if successful, otherwise null.
  static Future<Position?> getCurrentPosition() async {
    bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      return null;
    }

    LocationPermission permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied) {
        return null;
      }
    }

    if (permission == LocationPermission.deniedForever) {
      return null;
    }

    return await Geolocator.getCurrentPosition();
  }

  /// Get country name from coordinates.
  static Future<String?> getCountryFromPosition(Position position) async {
    try {
      List<Placemark> placemarks = await placemarkFromCoordinates(
        position.latitude,
        position.longitude,
      );
      if (placemarks.isNotEmpty) {
        return placemarks.first.country;
      }
    } catch (e) {
      print('Reverse geocoding error: $e');
    }
    return null;
  }

  /// High-level method: tries GPS, returns country name or null.
  static Future<String?> detectCountry() async {
    final pos = await getCurrentPosition();
    if (pos != null) {
      return await getCountryFromPosition(pos);
    }
    return null;
  }
}
