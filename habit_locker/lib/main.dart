import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_background_service/flutter_background_service.dart';
import 'package:flutter_background_service_android/flutter_background_service_android.dart';
import 'package:flutter_overlay_window/flutter_overlay_window.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:http/http.dart' as http;
import 'package:permission_handler/permission_handler.dart';

const String BACKEND_URL = "http://10.0.2.2:8000";

// --- ロックウィンドウの定義 ---
// 各エントリ: {'session': セッションID, 'habit': 習慣名, 'start': 開始時刻(時), 'end': 終了時刻(時)}
// セッションIDは「日付_セッション名」で一意に管理（例: "2024-03-10_morning"）
const List<Map<String, dynamic>> LOCK_WINDOWS = [
  {'session': 'morning', 'habit': 'bath', 'start': 6, 'end': 10,  'label': '⏰ 起床タイム'},
  {'session': 'evening', 'habit': 'bath', 'start': 18, 'end': 24, 'label': '🏠 帰宅タイム'},
];

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const MyApp());
}

// --- バックグラウンドサービス（別Isolate）---
@pragma('vm:entry-point')
void onStart(ServiceInstance service) async {
  debugPrint("[BGService] 起動しました");

  Timer.periodic(const Duration(minutes: 1), (timer) async {
    final now = DateTime.now();
    final prefs = await SharedPreferences.getInstance();
    final todayStr = "${now.year}-${now.month.toString().padLeft(2,'0')}-${now.day.toString().padLeft(2,'0')}";

    for (final window in LOCK_WINDOWS) {
      final sessionKey = "${todayStr}_${window['session']}";
      final alreadyDone = prefs.getBool(sessionKey) ?? false;

      final hour = now.hour;
      final inWindow = hour >= (window['start'] as int) && hour < (window['end'] as int);

      debugPrint("[BGService] セッション=${window['session']} 時刻=$hour "
          "ウィンドウ内=$inWindow 完了済=$alreadyDone");

      if (inWindow && !alreadyDone) {
        debugPrint("[BGService] 🔒 ロック発動: ${window['label']}");
        service.invoke('showLock', {
          'habit': window['habit'],
          'label': window['label'],
          'sessionKey': sessionKey,
        });
        break; // 一度に1セッションだけロック
      }
    }
  });
}

// --- オーバーレイ画面（SYSTEM_ALERT_WINDOW で全面表示）---
@pragma("vm:entry-point")
void overlayMain() {
  runZonedGuarded(() {
    debugPrint("[Overlay] overlayMain 呼び出し開始");
    WidgetsFlutterBinding.ensureInitialized();
    runApp(const MaterialApp(
      debugShowCheckedModeBanner: false,
      home: OverlayApp(),
    ));
  }, (error, stack) {
    debugPrint("[Overlay] CRITICAL ERROR: $error\n$stack");
  });
}

class OverlayApp extends StatefulWidget {
  const OverlayApp({super.key});
  @override
  State<OverlayApp> createState() => _OverlayAppState();
}

class _OverlayAppState extends State<OverlayApp> {
  bool isLoading = false;
  String errorMsg = "";

  Future<void> _checkIn() async {
    setState(() => isLoading = true);
    final prefs = await SharedPreferences.getInstance();
    final habit = prefs.getString('current_habit') ?? 'bath';
    final sessionKey = prefs.getString('current_session_key') ?? '';

    try {
      final res = await http.post(
        Uri.parse('$BACKEND_URL/checkin'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({"action": habit}),
      ).timeout(const Duration(seconds: 10));

      if (res.statusCode == 200) {
        // セッション完了を記録 → 今日はもうロックしない
        if (sessionKey.isNotEmpty) {
          await prefs.setBool(sessionKey, true);
        }
        await FlutterOverlayWindow.closeOverlay();
      } else {
        setState(() => errorMsg = "サーバーエラー: ${res.statusCode}");
      }
    } catch (e) {
      // オフライン対応：ネット不可でも解除できる（ローカルのみ記録）
      if (sessionKey.isNotEmpty) {
        await prefs.setBool(sessionKey, true);
      }
      await FlutterOverlayWindow.closeOverlay();
    } finally {
      setState(() => isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.red[900],
      child: SafeArea(
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.lock, size: 80, color: Colors.white),
              const SizedBox(height: 16),
              const Text(
                "🚨 風呂に入ってください 🚨",
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              const Text(
                "チェックインするまでスマホを使えません",
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.white70, fontSize: 14),
              ),
              const SizedBox(height: 32),
              if (errorMsg.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(bottom: 16),
                  child: Text(errorMsg, style: const TextStyle(color: Colors.yellow, fontSize: 14)),
                ),
              ElevatedButton.icon(
                icon: const Icon(Icons.check_circle),
                label: isLoading
                    ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Text("風呂上がりました！チェックイン", style: TextStyle(fontSize: 16)),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.white,
                  foregroundColor: Colors.red[900],
                  padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                onPressed: isLoading ? null : _checkIn,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// --- メインアプリ ---
class MyApp extends StatelessWidget {
  const MyApp({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Habit Locker',
      theme: ThemeData(
        primarySwatch: Colors.indigo,
        useMaterial3: true,
      ),
      home: const MonitoringScreen(),
    );
  }
}

class MonitoringScreen extends StatefulWidget {
  const MonitoringScreen({super.key});
  @override
  State<MonitoringScreen> createState() => _MonitoringScreenState();
}

class _MonitoringScreenState extends State<MonitoringScreen> {
  StreamSubscription? _lockSub;
  String _statusMsg = "初期化中...";
  List<String> _scheduleInfo = [];

  @override
  void initState() {
    super.initState();
    _initApp();
    _updateScheduleInfo();
  }

  void _updateScheduleInfo() {
    final now = DateTime.now();
    final todayStr = "${now.year}-${now.month.toString().padLeft(2,'0')}-${now.day.toString().padLeft(2,'0')}";
    setState(() {
      _scheduleInfo = LOCK_WINDOWS.map((w) {
        final start = w['start'].toString().padLeft(2, '0');
        final end = (w['end'] as int) >= 24 ? '翌0:00' : '${w['end'].toString().padLeft(2,'0')}:00';
        return "${w['label']}  $start:00 〜 $end";
      }).toList();
    });
  }

  Future<void> _initApp() async {
    await Permission.notification.request();
    bool overlayGranted = await FlutterOverlayWindow.isPermissionGranted();
    if (!overlayGranted) {
      await FlutterOverlayWindow.requestPermission();
    }
    setState(() => _statusMsg = "パーミッション確認済");

    final service = FlutterBackgroundService();
    await service.configure(
      androidConfiguration: AndroidConfiguration(
        onStart: onStart,
        autoStart: true,
        isForegroundMode: true,
      ),
      iosConfiguration: IosConfiguration(autoStart: false, onForeground: onStart),
    );

    final isRunning = await service.isRunning();
    if (!isRunning) {
      await service.startService();
    }
    setState(() => _statusMsg = "📡 バックグラウンドで監視中");

    _lockSub = service.on('showLock').listen((event) async {
      debugPrint("[MainUI] showLock 受信: $event");
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('current_habit', event?['habit'] ?? 'bath');
      await prefs.setString('current_session_key', event?['sessionKey'] ?? '');
      await _showLockOverlay();
    });
  }

  Future<void> _showLockOverlay() async {
    bool isActive = await FlutterOverlayWindow.isActive();
    if (!isActive) {
      await FlutterOverlayWindow.showOverlay(
        enableDrag: false,
        flag: OverlayFlag.focusPointer,
        alignment: OverlayAlignment.center,
        visibility: NotificationVisibility.visibilityPublic,
        positionGravity: PositionGravity.auto,
        height: WindowSize.fullCover,
        width: WindowSize.fullCover,
      );
    }
  }

  Future<void> _resetTodaySessions() async {
    final prefs = await SharedPreferences.getInstance();
    final now = DateTime.now();
    final todayStr = "${now.year}-${now.month.toString().padLeft(2,'0')}-${now.day.toString().padLeft(2,'0')}";
    for (final window in LOCK_WINDOWS) {
      await prefs.remove("${todayStr}_${window['session']}");
    }
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text("今日のセッションをリセットしました")),
    );
  }

  @override
  void dispose() {
    _lockSub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Habit Locker'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: "今日のセッションリセット",
            onPressed: _resetTodaySessions,
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Card(
              color: Colors.indigo[50],
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    const Icon(Icons.shield_rounded, size: 40, color: Colors.indigo),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(_statusMsg, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                          const Text("ロック時間帯に自動でロックされます", style: TextStyle(color: Colors.grey, fontSize: 12)),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),
            const Text("📅 本日のロック予定", style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            ..._scheduleInfo.map((info) => Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(
                children: [
                  const Icon(Icons.access_time, size: 18, color: Colors.indigo),
                  const SizedBox(width: 8),
                  Text(info, style: const TextStyle(fontSize: 15)),
                ],
              ),
            )),
            const Spacer(),
            // テストボタン
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                icon: const Icon(Icons.lock_outline),
                label: const Text("今すぐロックテスト"),
                onPressed: _showLockOverlay,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
