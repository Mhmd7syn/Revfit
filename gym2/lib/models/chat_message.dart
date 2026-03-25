class ChatMessage {
  final String text;
  final bool isUser;
  final DateTime timestamp;
  final String? intent;
  final bool? route;

  ChatMessage({
    required this.text,
    required this.isUser,
    required this.timestamp,
    this.intent,
    this.route,
  });

  factory ChatMessage.user(String text) {
    return ChatMessage(text: text, isUser: true, timestamp: DateTime.now());
  }

  factory ChatMessage.bot(String text, {String? intent, bool? route}) {
    return ChatMessage(
      text: text,
      isUser: false,
      timestamp: DateTime.now(),
      intent: intent,
      route: route,
    );
  }
}
