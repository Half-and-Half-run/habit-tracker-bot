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

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const MyApp());
}

// --- バックグラウンドサービス（別Isolate、シグナルのみ送信）---
@pragma('vm:entry-point')
void onStart(ServiceInstance service) async {
  debugPrint("[BGService] 起動しました");
  Timer.periodic(const Duration(minutes: 1), (timer) {
    debugPrint("[BGService] タイマー発火 → showLock を送信");
    service.invoke('showLock', {'habit': 'wake'});
  });
}

// --- オーバーレイ画面（SYSTEM_ALERT_WINDOW で全面表示）---
@pragma("vm:entry-point")
void overlayMain() {
  debugPrint("[Overlay] overlayMain 呼び出し開始");
  WidgetsFlutterBinding.ensureInitialized();
  debugPrint("[Overlay] WidgetsFlutterBinding 初期化完了");
  runApp(const MaterialApp(
    debugShowCheckedModeBanner: false,
    home: OverlayApp(),
  ));
  debugPrint("[Overlay] runApp 完了");
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
                  child: Text(errorMsg, style: const TextStyle(color: Colors.yellow)),
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
  String _statusMsg = "初期化中...";

  @override
  void initState() {
    super.initState();
    _initApp();
  }

  Future<void> _initApp() async {
    // パーミッション要求
    await Permission.notification.request();
    bool overlayGranted = await FlutterOverlayWindow.isPermissionGranted();
    if (!overlayGranted) {
      await FlutterOverlayWindow.requestPermission();
    }
    setState(() => _statusMsg = "パーミッション確認済");

    // バックグラウンドサービス設定&起動
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
      debugPrint("[MainUI] バックグラウンドサービスを起動しました");
    } else {
      debugPrint("[MainUI] バックグラウンドサービスは既に起動中");
    }
    setState(() => _statusMsg = "バックグラウンドで監視中です");

    // バックグラウンドサービスからの showLock イベントをリッスン
    _lockSub = service.on('showLock').listen((event) async {
      debugPrint("[MainUI] showLock 受信: $event → オーバーレイ表示");
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('current_habit', event?['habit'] ?? 'wake');
      await _showLockOverlay();
    });
  }

  Future<void> _showLockOverlay() async {
    bool isActive = await FlutterOverlayWindow.isActive();
    if (!isActive) {
      debugPrint("[MainUI] FlutterOverlayWindow.showOverlay() を呼び出し中...");
      await FlutterOverlayWindow.showOverlay(
        enableDrag: false,
        flag: OverlayFlag.focusPointer,
        alignment: OverlayAlignment.center,
        visibility: NotificationVisibility.visibilityPublic,
        positionGravity: PositionGravity.auto,
        height: WindowSize.fullCover,
        width: WindowSize.fullCover,
      );
      debugPrint("[MainUI] showOverlay 完了");
    }
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
          children: [
            const Icon(Icons.shield_rounded, size: 80, color: Colors.indigo),
            const SizedBox(height: 20),
            Text(
              _statusMsg,
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 10),
            const Text(
              "時間になると自動でロックされます。",
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.grey),
            ),
            const SizedBox(height: 30),
            // デバッグ用：今すぐロックボタン
            ElevatedButton.icon(
              icon: const Icon(Icons.lock),
              label: const Text("今すぐロック（テスト）"),
              onPressed: _showLockOverlay,
            ),
          ],
        ),
      ),
    );
  }
}
