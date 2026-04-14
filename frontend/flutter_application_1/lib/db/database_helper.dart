import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart';
import '../models/inventory_item.dart';

class DatabaseHelper {
  static final DatabaseHelper instance = DatabaseHelper._init();
  static Database? _database;

  DatabaseHelper._init();

  Future<Database> get database async {
    _database ??= await _initDB('pantrai.db');
    return _database!;
  }

  Future<Database> _initDB(String fileName) async {
    final dbPath = await getDatabasesPath();
    final path = join(dbPath, fileName);
    return openDatabase(path, version: 1, onCreate: _createDB);
  }

  Future<void> _createDB(Database db, int version) async {
    await db.execute('''
      CREATE TABLE inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        generic_name TEXT NOT NULL,
        quantity INTEGER NOT NULL
      )
    ''');
  }

  Future<List<InventoryItem>> getAllItems() async {
    final db = await database;
    final rows = await db.query('inventory', orderBy: 'name ASC');
    return rows.map(InventoryItem.fromMap).toList();
  }

  // If an item with the same name already exists, increment its quantity.
  // Otherwise insert a new row.
  Future<void> upsertItem(String name, String genericName, int quantity) async {
    final db = await database;
    final existing = await db.query(
      'inventory',
      where: 'name = ?',
      whereArgs: [name],
    );
    if (existing.isNotEmpty) {
      final id = existing.first['id'] as int;
      final newQty = (existing.first['quantity'] as int) + quantity;
      await db.update(
        'inventory',
        {'quantity': newQty},
        where: 'id = ?',
        whereArgs: [id],
      );
    } else {
      await db.insert('inventory', {
        'name': name,
        'generic_name': genericName,
        'quantity': quantity,
      });
    }
  }

  Future<void> updateQuantity(int id, int quantity) async {
    final db = await database;
    await db.update(
      'inventory',
      {'quantity': quantity},
      where: 'id = ?',
      whereArgs: [id],
    );
  }

  Future<void> deleteItem(int id) async {
    final db = await database;
    await db.delete('inventory', where: 'id = ?', whereArgs: [id]);
  }
}
