import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_background_service/flutter_background_service.dart';
import 'package:flutter_background_service_android/flutter_background_service_android.dart';
import 'package:flutter_overlay_window/flutter_overlay_window.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:http/http.dart' as http;
import 'package:permission_handler/permission_handler.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart' hide NotificationVisibility;

// ★バックエンドのURLをここに直接指定します（設定画面からの入力を不要にするため）
// 実際のスマホから連携させる場合は、このURLをご自身のPCのIPアドレス（例: http://192.168.x.x:8000）やngrokのURLに変更してください。
// エミュレータでテストする場合は http://10.0.2.2:8000 を使用します。
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

  const AndroidNotificationChannel channel = AndroidNotificationChannel(
    'habit_locker_channel', // AndroidManifestのサービスと一致させるID
    'Habit Locker Service', // タイトル
    description: 'This channel is used for background locker monitoring.',
    importance: Importance.high, 
  );

  final flutterLocalNotificationsPlugin = FlutterLocalNotificationsPlugin();

  // Android用の通知チャネルを作成
  await flutterLocalNotificationsPlugin
      .resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()
      ?.createNotificationChannel(channel);

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
    // APIのURLが設定されていなければ何もしない
    if (BACKEND_URL.isEmpty) return;

    final now = DateTime.now();
    final currentMinutes = now.hour * 60 + now.minute;

    // 起床(9:00 = 540分), 入浴(23:00 = 1380分)
    try {
      final res = await http.get(Uri.parse('$BACKEND_URL/status'));
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
    final habit = prefs.getString('current_habit') ?? 'wake';

    try {
      final res = await http.post(
        Uri.parse('$BACKEND_URL/checkin'),
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
  @override
  void initState() {
    super.initState();
    _initializeApp();
  }

  Future<void> _initializeApp() async {
    await _requestPermissions();
    await initializeService();
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
              "URLの設定は不要です。\n帰宅後、時間になると勝手にロックされます。",
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.grey),
            )
          ],
        ),
      ),
    );
  }
}
