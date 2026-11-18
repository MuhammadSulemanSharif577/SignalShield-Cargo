import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';

typedef TestReply = ({int status, Map<String, dynamic>? body});

class TestAdapter implements HttpClientAdapter {
  TestAdapter(this.respond);

  final TestReply Function(RequestOptions) respond;
  final requests = <RequestOptions>[];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requests.add(options);
    final reply = respond(options);
    return ResponseBody.fromString(
      reply.body == null ? '' : jsonEncode(reply.body),
      reply.status,
      headers: {Headers.contentTypeHeader: [Headers.jsonContentType]},
    );
  }

  @override
  void close({bool force = false}) {}
}

Map<String, dynamic> sessionResponse({
  String token = 'session-token',
  bool mustChangePassword = false,
  String? driverId = 'd1',
}) => {
  'token': token,
  'expiresAt': '2099-01-01T00:00:00Z',
  'user': {
    'id': '1',
    'name': 'Driver One',
    'email': 'driver@example.com',
    'driverId': driverId,
    'mustChangePassword': mustChangePassword,
  },
  'roleNames': ['Driver'],
  'permissions': mustChangePassword ? [] : ['driver:access'],
};
