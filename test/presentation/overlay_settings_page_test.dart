import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:traductor/app/luma_app.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const channel = MethodChannel('luma/screen_translator');
  late List<MethodCall> calls;
  late bool running;
  late bool denied;

  setUp(() {
    calls = [];
    running = false;
    denied = false;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
          calls.add(call);
          if (call.method == 'start') {
            if (denied) {
              throw PlatformException(
                code: 'permission',
                message: 'Captura cancelada por el usuario',
              );
            }
            running = true;
          }
          if (call.method == 'stop') running = false;
          if (call.method == 'status') {
            return {
              'running': running,
              'original': false,
              'message': running ? 'Barra activa' : 'Captura detenida',
            };
          }
          return null;
        });
  });
  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, null);
  });

  Future<void> mount(
    WidgetTester tester, {
    TargetPlatform platform = TargetPlatform.windows,
    Size size = const Size(820, 900),
  }) async {
    tester.view.devicePixelRatio = 1;
    tester.view.physicalSize = size;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(LumaApp(platform: platform));
    await tester.pumpAndSettle();
  }

  Future<void> showStart(WidgetTester tester) async {
    await tester.scrollUntilVisible(
      find.byKey(const Key('start-overlay')),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
  }

  testWidgets(
    'Windows defaults to offline translation and sends real capture options',
    (tester) async {
      await mount(tester);
      await showStart(tester);
      expect(
        tester
            .widget<FilledButton>(find.byKey(const Key('start-overlay')))
            .onPressed,
        isNotNull,
      );
      expect(find.byType(CheckboxListTile), findsNothing);
      await tester.tap(find.byKey(const Key('start-overlay')));
      await tester.pumpAndSettle();
      final start = calls.singleWhere((call) => call.method == 'start');
      expect(start.arguments['source'], 'en');
      expect(start.arguments['target'], 'es');
      expect(start.arguments.containsKey('automatic'), isFalse);
      expect(calls.where((call) => call.method == 'translate'), isEmpty);
      expect(start.arguments['provider'], 'local');
      expect(find.text('Barra activa'), findsOneWidget);
      await tester.ensureVisible(find.text('Traducir ahora'));
      await tester.tap(find.text('Traducir ahora'));
      await tester.pumpAndSettle();
      expect(calls.where((call) => call.method == 'translate'), hasLength(1));
      await tester.pump(const Duration(seconds: 12));
      expect(calls.where((call) => call.method == 'translate'), hasLength(1));
      await tester.ensureVisible(find.text('Detener y cerrar la barra'));
      await tester.tap(find.text('Detener y cerrar la barra'));
      await tester.pumpAndSettle();
      expect(calls.where((call) => call.method == 'stop'), hasLength(1));
      expect(find.text('Activar barra flotante'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('An explicitly selected online provider requires consent', (
    tester,
  ) async {
    await mount(tester);
    final provider = find.byKey(const Key('translation-provider'));
    await tester.scrollUntilVisible(
      provider.hitTestable(),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    await tester.tap(provider);
    await tester.pumpAndSettle();
    await tester.tap(find.text('MyMemory · sin clave').last);
    await tester.pumpAndSettle();
    await showStart(tester);
    expect(
      tester
          .widget<FilledButton>(find.byKey(const Key('start-overlay')))
          .onPressed,
      isNull,
    );
    await tester.ensureVisible(find.byType(CheckboxListTile));
    await tester.tap(find.byType(CheckboxListTile));
    await tester.pumpAndSettle();
    await showStart(tester);
    await tester.tap(find.byKey(const Key('start-overlay')));
    await tester.pumpAndSettle();
    expect(
      calls.singleWhere((call) => call.method == 'start').arguments['provider'],
      'mymemory',
    );
  });

  testWidgets(
    'Android requests native capture without sending text to a provider',
    (tester) async {
      await mount(
        tester,
        platform: TargetPlatform.android,
        size: const Size(390, 844),
      );
      expect(find.byType(CheckboxListTile), findsNothing);
      await tester.scrollUntilVisible(
        find.text('Traducción en el dispositivo'),
        300,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.text('Traducción en el dispositivo'), findsOneWidget);
      await showStart(tester);
      await tester.tap(find.byKey(const Key('start-overlay')));
      await tester.pumpAndSettle();
      expect(calls.where((call) => call.method == 'start'), hasLength(1));
      expect(find.text('Barra activa'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'Denied capture is shown and never claims the overlay is active',
    (tester) async {
      denied = true;
      await mount(tester, platform: TargetPlatform.android);
      await showStart(tester);
      await tester.tap(find.byKey(const Key('start-overlay')));
      await tester.pumpAndSettle();
      expect(find.text('Captura cancelada por el usuario'), findsOneWidget);
      expect(find.text('Detener y cerrar la barra'), findsNothing);
      expect(
        tester
            .widget<FilledButton>(find.byKey(const Key('start-overlay')))
            .onPressed,
        isNotNull,
      );
    },
  );

  for (final size in [
    const Size(320, 720),
    const Size(390, 844),
    const Size(820, 900),
  ]) {
    testWidgets('Settings fit ${size.width} px without overflow', (
      tester,
    ) async {
      await mount(tester, size: size);
      await showStart(tester);
      expect(tester.takeException(), isNull);
    });
  }
}
