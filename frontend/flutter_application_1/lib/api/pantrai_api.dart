import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import '../constants.dart';

class BarcodeItemResult {
  final String itemName;
  BarcodeItemResult({required this.itemName});
}

class ExtractedItem {
  final String name;
  final String genericName;
  int quantity;

  ExtractedItem({
    required this.name,
    required this.genericName,
    required this.quantity,
  });
}

class ReceiptResult {
  final String? store;
  final String? date;
  final List<ExtractedItem> items;

  ReceiptResult({this.store, this.date, required this.items});
}

class PantrAIApi {
  static Future<BarcodeItemResult> getBarcodeItem(String barcode) async {
    final uri = Uri.parse('$kBackendBaseUrl/get-barcode-item');
    final response = await http
        .post(
          uri,
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'barcode': barcode}),
        )
        .timeout(kApiTimeout);

    if (response.statusCode != 200) {
      throw Exception('Barcode lookup failed (HTTP ${response.statusCode})');
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;
    return BarcodeItemResult(itemName: data['item-name'] as String);
  }

  static Future<List<ExtractedItem>> extractItems(File imageFile) async {
    final uri = Uri.parse('$kBackendBaseUrl/extract-items');
    final bytes = await imageFile.readAsBytes();
    final b64 = base64Encode(bytes);

    final response = await http
        .post(
          uri,
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'images': [b64],
          }),
        )
        .timeout(kApiTimeout);

    if (response.statusCode != 200) {
      throw Exception('Item extraction failed (HTTP ${response.statusCode})');
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;
    final results = data['results'] as List<dynamic>;
    if (results.isEmpty || results.first == null) return [];

    final first = results.first as Map<String, dynamic>;
    final items = first['items'] as List<dynamic>;
    return items.map((e) {
      final m = e as Map<String, dynamic>;
      return ExtractedItem(
        name: m['name'] as String,
        genericName: m['generic_name'] as String,
        quantity: (m['quantity'] as num).toInt(),
      );
    }).toList();
  }

  static Future<ReceiptResult> extractReceipts(File imageFile) async {
    final uri = Uri.parse('$kBackendBaseUrl/extract-receipts');
    final bytes = await imageFile.readAsBytes();
    final b64 = base64Encode(bytes);

    final response = await http
        .post(
          uri,
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'images': [b64],
          }),
        )
        .timeout(kApiTimeout);

    if (response.statusCode != 200) {
      throw Exception('Receipt extraction failed (HTTP ${response.statusCode})');
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;
    final results = data['results'] as List<dynamic>;
    if (results.isEmpty || results.first == null) {
      return ReceiptResult(items: []);
    }

    final first = results.first as Map<String, dynamic>;
    final items = (first['items'] as List<dynamic>).map((e) {
      final m = e as Map<String, dynamic>;
      return ExtractedItem(
        name: m['name'] as String,
        genericName: m['generic_name'] as String,
        quantity: (m['quantity'] as num).toInt(),
      );
    }).toList();

    return ReceiptResult(
      store: first['store'] as String?,
      date: first['date'] as String?,
      items: items,
    );
  }
}
