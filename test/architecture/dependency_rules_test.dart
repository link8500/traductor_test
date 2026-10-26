import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Production layers depend inward and have no import cycles', () {
    final root = Directory('lib').absolute.uri;
    final sources = Directory('lib')
        .listSync(recursive: true)
        .whereType<File>()
        .where((file) => file.path.endsWith('.dart'));
    const allowed = {
      'domain': {'domain'},
      'application': {'application', 'domain'},
      'infrastructure': {'infrastructure', 'domain'},
      'presentation': {'presentation', 'application', 'domain'},
      'app': {'app', 'application', 'domain', 'infrastructure', 'presentation'},
      'main.dart': {'app'},
    };
    final imports = RegExp(r'''(?:import|export|part)\s+['"]([^'"]+)['"]''');
    final graph = <String, List<String>>{};
    for (final file in sources) {
      final relative = file.absolute.uri;
      final path = file.absolute.uri.path.substring(root.path.length);
      final layer = path.split('/').first;
      expect(
        allowed.containsKey(layer),
        isTrue,
        reason: 'Unassigned layer: $path',
      );
      graph[path] = [];
      for (final match in imports.allMatches(file.readAsStringSync())) {
        final import = match.group(1)!;
        if (layer == 'domain' || layer == 'application') {
          expect(
            import.startsWith('dart:') ||
                !Uri.parse(import).hasScheme ||
                import.startsWith('package:traductor/'),
            isTrue,
            reason: '$path must remain independent of frameworks: $import',
          );
        }
        if (import.startsWith('dart:') ||
            (import.startsWith('package:') &&
                !import.startsWith('package:traductor/'))) {
          continue;
        }
        final target = import.startsWith('package:traductor/')
            ? root.resolve(import.substring('package:traductor/'.length))
            : relative.resolve(import);
        expect(
          File.fromUri(target).existsSync(),
          isTrue,
          reason: '$path imports missing $import',
        );
        final targetPath = target.path.substring(root.path.length);
        expect(
          allowed[layer],
          contains(targetPath.split('/').first),
          reason: '$path points outward to $targetPath',
        );
        graph[path]!.add(targetPath);
      }
    }
    final visited = <String>{};
    final active = <String>{};
    void visit(String path) {
      expect(
        active,
        isNot(contains(path)),
        reason: 'Circular dependency at $path',
      );
      if (!visited.add(path)) return;
      active.add(path);
      for (final target in graph[path] ?? <String>[]) {
        visit(target);
      }
      active.remove(path);
    }

    graph.keys.forEach(visit);
  });
}
