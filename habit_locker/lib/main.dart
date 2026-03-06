import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_background_service/flutter_background_service.dart';
import 'package:flutter_background_service_android/flutter_background_service_android.dart';
import 'package:flutter_overlay_window/flutter_overlay_window.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:http/http.dart' as http;
import 'package:permission_handler/permission_handler.dart';

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
      notificationChannelId: 'habit_locker_channel',
      initialNotificationTitle: 'Habit Locker Active',
      initialNotificationContent: 'Monitoring deadlines...',
      foregroundServiceNotificationId: 888,
    ),
    iosConfiguration: IosConfiguration(
      autoStart: false,
      onForeground: onStart,
    ),
  );
}

@pragma('vm:entry-point')
void onStart(ServiceInstance service) async {
  Timer.periodic(const Duration(minutes: 1), (timer) async {
    final prefs = await SharedPreferences.getInstance();
    final baseUrl = prefs.getString('api_url') ?? '';
    // APIのURLが設定されていなければ何もしない
    if (baseUrl.isEmpty) return;

    final now = DateTime.now();
    final currentMinutes = now.hour * 60 + now.minute;

    // 起床(9:00 = 540分), 入浴(23:00 = 1380分)
    try {
      final res = await http.get(Uri.parse('$baseUrl/status'));
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        final todayRecord = data['today_record'];
        
        bool needsWakeCheckin = (currentMinutes >= 540) && (todayRecord['wake_time'] == null);
        bool needsBathCheckin = (currentMinutes >= 1380) && (todayRecord['bath_time'] == null);

        if (needsWakeCheckin || needsBathCheckin) {
          bool isActive = await FlutterOverlayWindow.isActive();
          if (!isActive) {
            String targetAction = needsWakeCheckin ? "wake" : "bath";
            prefs.setString('current_habit', targetAction);
            
            // システムオーバーレイとして全画面に強制表示！
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
      }
    } catch (e) {
      debugPrint("エラー: $e");
    }
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
    final baseUrl = prefs.getString('api_url') ?? '';
    final habit = prefs.getString('current_habit') ?? 'wake';

    try {
      final res = await http.post(
        Uri.parse('$baseUrl/checkin'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({"action": habit}),
      );
      if (res.statusCode == 200) {
        // チェックイン成功！オーバーレイを閉じて解放する
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
        backgroundColor: Colors.red[900], // 警告の赤色
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
                    : const Text("今すぐチェックインして解放する", style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              )
            ],
          ),
        ),
      ),
    );
  }
}

// --- 通常のアプリ画面（初期設定用） ---
class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Habit Locker',
      theme: ThemeData(primarySwatch: Colors.indigo),
      home: const SettingsScreen(),
    );
  }
}

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final TextEditingController _urlController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _initializeApp();
  }

  Future<void> _initializeApp() async {
    await _loadUrl();
    await _requestPermissions();
    await initializeService();
  }

  Future<void> _loadUrl() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      _urlController.text = prefs.getString('api_url') ?? '';
    });
  }

  Future<void> _saveUrl() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('api_url', _urlController.text);
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text("API URLを保存しました")),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('設定')),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            const Text("バックエンドサーバーのURLを入力してください（例: https://xxx.ngrok-free.app）"),
            const SizedBox(height: 10),
            TextField(
              controller: _urlController,
              decoration: const InputDecoration(border: OutlineInputBorder(), labelText: "API URL"),
            ),
            const SizedBox(height: 20),
            ElevatedButton(
              onPressed: _saveUrl,
              child: const Text("保存して監視を開始"),
            ),
          ],
        ),
      ),
    );
  }
}
