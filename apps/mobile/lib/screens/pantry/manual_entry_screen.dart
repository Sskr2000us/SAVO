import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../services/api_client.dart';
import '../../widgets/quantity_picker.dart';

/// Screen for manually adding ingredients without scanning
class ManualEntryScreen extends StatefulWidget {
  const ManualEntryScreen({Key? key}) : super(key: key);

  @override
  State<ManualEntryScreen> createState() => _ManualEntryScreenState();
}

class _ManualEntryScreenState extends State<ManualEntryScreen> {
  final TextEditingController _ingredientController = TextEditingController();
  final FocusNode _ingredientFocus = FocusNode();
  
  double _quantity = 1.0;
  String _unit = 'pieces';
  bool _isSubmitting = false;
  
  // Common ingredients for quick add
  final List<String> _commonIngredients = [
    'tomato',
    'onion',
    'garlic',
    'potato',
    'carrot',
    'bell_pepper',
    'chicken',
    'beef',
    'rice',
    'pasta',
    'milk',
    'eggs',
    'cheese',
    'butter',
    'oil',
    'salt',
    'pepper',
    'flour',
    'sugar',
  ];
  
  List<String> _filteredIngredients = [];
  bool _showSuggestions = false;

  @override
  void initState() {
    super.initState();
    _filteredIngredients = _commonIngredients;
    _ingredientController.addListener(_onIngredientChanged);
  }

  @override
  void dispose() {
    _ingredientController.dispose();
    _ingredientFocus.dispose();
    super.dispose();
  }

  String _canonicalizeName(String display) {
    final trimmed = display.trim().toLowerCase();
    final collapsed = trimmed.replaceAll(RegExp(r'\s+'), '_');
    return collapsed;
  }

  void _onIngredientChanged() {
    final query = _ingredientController.text.toLowerCase();
    setState(() {
      if (query.isEmpty) {
        _filteredIngredients = _commonIngredients;
        _showSuggestions = false;
      } else {
        _filteredIngredients = _commonIngredients
            .where((ing) => ing.toLowerCase().contains(query))
            .toList();
        _showSuggestions = true;
      }
      
      // Update smart unit suggestions based on ingredient name
      if (query.isNotEmpty) {
        final smartUnits = getSmartUnitSuggestions(null, query);
        if (!smartUnits.contains(_unit)) {
          _unit = smartUnits.first;
        }
      }
    });
  }

  void _selectIngredient(String ingredient) {
    setState(() {
      _ingredientController.text = ingredient.replaceAll('_', ' ');
      _showSuggestions = false;
      
      // Update unit suggestions
      final smartUnits = getSmartUnitSuggestions(null, ingredient);
      _unit = smartUnits.first;
    });
    _ingredientFocus.unfocus();
  }

  Future<void> _submitIngredient() async {
    final ingredientName = _ingredientController.text.trim();
    
    if (ingredientName.isEmpty) {
      _showError('Please enter an ingredient name');
      return;
    }
    
    setState(() {
      _isSubmitting = true;
    });

    try {
      final apiClient = Provider.of<ApiClient>(context, listen: false);
      await apiClient.post('/inventory-db/items', {
        'canonical_name': _canonicalizeName(ingredientName),
        'display_name': ingredientName,
        'quantity': _quantity,
        'unit': _unit,
        'storage_location': 'pantry',
        'item_state': 'raw',
        'source': 'manual',
        'notes': null,
      });

      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Item added to inventory'),
          backgroundColor: Colors.green,
          duration: Duration(seconds: 2),
        ),
      );

      setState(() {
        _ingredientController.clear();
        _quantity = 1.0;
        _unit = 'pieces';
        _showSuggestions = false;
      });

      Future.delayed(const Duration(milliseconds: 300), () {
        if (mounted) {
          Navigator.of(context).pop(true);
        }
      });
    } catch (e) {
      _showError('Failed to add ingredient: $e');
    } finally {
      if (mounted) {
        setState(() {
          _isSubmitting = false;
        });
      }
    }
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: Colors.red,
        duration: const Duration(seconds: 3),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Add Ingredient Manually'),
        backgroundColor: const Color(0xFF4CAF50),
        actions: [
          IconButton(
            icon: const Icon(Icons.help_outline),
            onPressed: () {
              showDialog(
                context: context,
                builder: (context) => AlertDialog(
                  title: const Text('Manual Entry Help'),
                  content: const Text(
                    'Quickly add ingredients to your pantry without scanning:\n\n'
                    '1. Type the ingredient name\n'
                    '2. Adjust quantity and unit\n'
                    '3. Tap "Add to Pantry"\n\n'
                    'Tip: Use this when items don\'t scan well or for bulk entry.',
                  ),
                  actions: [
                    TextButton(
                      onPressed: () => Navigator.pop(context),
                      child: const Text('Got it'),
                    ),
                  ],
                ),
              );
            },
          ),
        ],
      ),
      body: GestureDetector(
        onTap: () {
          _ingredientFocus.unfocus();
          setState(() {
            _showSuggestions = false;
          });
        },
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Info card
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.blue.shade50,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: Colors.blue.shade200),
                ),
                child: Row(
                  children: [
                    Icon(Icons.info_outline, color: Colors.blue.shade700),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        'Manually add ingredients that are difficult to scan',
                        style: TextStyle(
                          color: Colors.blue.shade900,
                          fontSize: 14,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              
              const SizedBox(height: 24),
              
              // Ingredient name input
              const Text(
                'Ingredient Name',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),
              Stack(
                children: [
                  TextField(
                    controller: _ingredientController,
                    focusNode: _ingredientFocus,
                    decoration: InputDecoration(
                      hintText: 'e.g., tomato, onion, chicken',
                      prefixIcon: const Icon(Icons.search),
                      suffixIcon: _ingredientController.text.isNotEmpty
                          ? IconButton(
                              icon: const Icon(Icons.clear),
                              onPressed: () {
                                _ingredientController.clear();
                                setState(() {
                                  _showSuggestions = false;
                                });
                              },
                            )
                          : null,
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(12),
                        borderSide: const BorderSide(
                          color: Color(0xFF4CAF50),
                          width: 2,
                        ),
                      ),
                    ),
                    onTap: () {
                      setState(() {
                        _showSuggestions = true;
                      });
                    },
                    onSubmitted: (_) {
                      setState(() {
                        _showSuggestions = false;
                      });
                    },
                  ),
                  
                  // Suggestions dropdown
                  if (_showSuggestions && _filteredIngredients.isNotEmpty)
                    Positioned(
                      top: 60,
                      left: 0,
                      right: 0,
                      child: Material(
                        elevation: 4,
                        borderRadius: BorderRadius.circular(12),
                        child: Container(
                          constraints: const BoxConstraints(maxHeight: 200),
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(color: Colors.grey.shade300),
                          ),
                          child: ListView.builder(
                            shrinkWrap: true,
                            padding: EdgeInsets.zero,
                            itemCount: _filteredIngredients.length,
                            itemBuilder: (context, index) {
                              final ingredient = _filteredIngredients[index];
                              return ListTile(
                                leading: const Icon(Icons.inventory_2_outlined),
                                title: Text(
                                  ingredient.replaceAll('_', ' '),
                                  style: const TextStyle(fontSize: 14),
                                ),
                                onTap: () => _selectIngredient(ingredient),
                              );
                            },
                          ),
                        ),
                      ),
                    ),
                ],
              ),
              
              const SizedBox(height: 24),
              
              // Quantity section
              const Text(
                'Quantity',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  border: Border.all(color: Colors.grey.shade300),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Center(
                  child: QuantityPicker(
                    initialQuantity: _quantity,
                    initialUnit: _unit,
                    availableUnits: getSmartUnitSuggestions(
                      null,
                      _ingredientController.text,
                    ),
                    onChanged: (qty, unit) {
                      setState(() {
                        _quantity = qty;
                        _unit = unit;
                      });
                    },
                    enabled: true,
                  ),
                ),
              ),
              
              const SizedBox(height: 32),
              
              // Submit button
              ElevatedButton(
                onPressed: _isSubmitting ? null : _submitIngredient,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF4CAF50),
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  elevation: 2,
                ),
                child: _isSubmitting
                    ? const SizedBox(
                        height: 20,
                        width: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                        ),
                      )
                    : Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: const [
                          Icon(Icons.add_circle_outline, size: 24),
                          SizedBox(width: 8),
                          Text(
                            'Add to Pantry',
                            style: TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ],
                      ),
              ),
              
              const SizedBox(height: 16),
              
              // Quick add section
              if (!_showSuggestions) ...[
                const Divider(height: 32),
                const Text(
                  'Quick Add Common Items',
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: Colors.grey,
                  ),
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: _commonIngredients.take(12).map((ingredient) {
                    return ActionChip(
                      label: Text(
                        ingredient.replaceAll('_', ' '),
                        style: const TextStyle(fontSize: 13),
                      ),
                      onPressed: () => _selectIngredient(ingredient),
                      backgroundColor: Colors.grey.shade100,
                    );
                  }).toList(),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
