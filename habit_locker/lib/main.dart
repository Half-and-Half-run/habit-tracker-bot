import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_background_service/flutter_background_service.dart';
import 'package:flutter_background_service_android/flutter_background_service_android.dart';
import 'package:flutter_overlay_window/flutter_overlay_window.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:http/http.dart' as http;
import 'package:permission_handler/permission_handler.dart';

// ★バックエンドのURL
// エミュレータでテストする場合は http://10.0.2.2:8000 を使用します。
// 実機の場合は自分のPCのIPアドレス（例: http://192.168.x.x:8000）やngrokのURLに変更してください。
const String BACKEND_URL = "http://10.0.2.2:8000";

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const MyApp());
}

Future<void> _requestPermissions() async {
  await Permission.notification.request();
  bool isOverlayGranted = await FlutterOverlayWindow.isPermissionGranted();
  if (!isOverlayGranted) {
    await FlutterOverlayWindow.requestPermission();
  }
}

Future<void> initializeService() async {
  final service = FlutterBackgroundService();
  await service.configure(
    androidConfiguration: AndroidConfiguration(
      onStart: onStart,
      autoStart: true,
      isForegroundMode: true,
    ),
    iosConfiguration: IosConfiguration(
      autoStart: false,
      onForeground: onStart,
    ),
  );
  await service.startService();
}

// バックグラウンドサービス本体（別Dart Isolateで動作）
// ※このIsolateからは FlutterOverlayWindow が使えないため、
//   メインIsolateに 'showLock' イベントを送信して表示依頼する。
@pragma('vm:entry-point')
void onStart(ServiceInstance service) async {
  debugPrint("[BGService] バックグラウンドサービス開始");
  Timer.periodic(const Duration(minutes: 1), (timer) async {
    debugPrint("[BGService] タイマー発火: チェック中...");
    // ★ テスト用: 常時ロック（API接続なし）
    // メインIsolateに 'showLock' イベントを送って、UI側でオーバーレイを表示させる
    service.invoke('showLock', {'habit': 'wake'});
  });
}

// --- システムオーバーレイ（強制ロック画面）のエントリーポイント ---
@pragma("vm:entry-point")
void overlayMain() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const OverlayApp());
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
    final habit = prefs.getString('current_habit') ?? 'wake';
    try {
      final res = await http.post(
        Uri.parse('$BACKEND_URL/checkin'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({"action": habit}),
      );
      if (res.statusCode == 200) {
        await FlutterOverlayWindow.closeOverlay();
      } else {
        setState(() => errorMsg = "エラー: ${res.statusCode}");
      }
    } catch (e) {
      setState(() => errorMsg = "通信エラー: $e");
    } finally {
      setState(() => isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      home: Scaffold(
        backgroundColor: Colors.red[900],
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.warning_amber_rounded, size: 100, color: Colors.white),
              const SizedBox(height: 20),
              const Text(
                "🚨 締め切りオーバー 🚨\nチェックインするまでスマホを使えません",
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 40),
              if (errorMsg.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(bottom: 20),
                  child: Text(errorMsg, style: const TextStyle(color: Colors.yellow, fontSize: 16)),
                ),
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.white,
                  foregroundColor: Colors.red[900],
                  padding: const EdgeInsets.symmetric(horizontal: 40, vertical: 20),
                ),
                onPressed: isLoading ? null : _checkIn,
                child: isLoading
                    ? const CircularProgressIndicator()
                    : const Text("今すぐチェックインして解放する",
                        style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              )
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
      theme: ThemeData(primarySwatch: Colors.indigo),
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

  @override
  void initState() {
    super.initState();
    _initializeApp();
  }

  Future<void> _initializeApp() async {
    await _requestPermissions();
    await initializeService();

    // バックグラウンドサービスからの 'showLock' イベントをメインIsolateでリッスンする
    final service = FlutterBackgroundService();
    _lockSub = service.on('showLock').listen((event) async {
      debugPrint("[MainUI] showLock イベント受信: $event");
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('current_habit', event?['habit'] ?? 'wake');
      bool isActive = await FlutterOverlayWindow.isActive();
      if (!isActive) {
        debugPrint("[MainUI] オーバーレイを表示します");
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
    });
  }

  @override
  void dispose() {
    _lockSub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Habit Locker')),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: const [
            Icon(Icons.shield_rounded, size: 80, color: Colors.indigo),
            SizedBox(height: 20),
            Text(
              "バックグラウンドで監視中です",
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
            SizedBox(height: 10),
            Text(
              "URLの設定は不要です。\n時間になると勝手にロックされます。",
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.grey),
            ),
          ],
        ),
      ),
    );
  }
}
