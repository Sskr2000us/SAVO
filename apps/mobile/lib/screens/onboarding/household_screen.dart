import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../models/profile_state.dart';
import '../../services/profile_service.dart';
import '../../services/api_client.dart';
import '../../services/onboarding_storage.dart';
import 'onboarding_coordinator.dart';

class OnboardingHouseholdScreen extends StatefulWidget {
  const OnboardingHouseholdScreen({super.key});

  @override
  State<OnboardingHouseholdScreen> createState() =>
      _OnboardingHouseholdScreenState();
}

class _OnboardingHouseholdScreenState extends State<OnboardingHouseholdScreen> {
  final List<Map<String, dynamic>> _members = [];
  bool _isLoading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadExistingMembers();
  }

  void _loadExistingMembers() {
    final profileState = Provider.of<ProfileState>(context, listen: false);
    if (profileState.members.isNotEmpty) {
      setState(() {
        _members.addAll(profileState.members.cast<Map<String, dynamic>>());
      });
    }
  }

  void _addMember() {
    setState(() {
      _members.add({
        'name': '',
        'age': 30,
        'role': 'adult',
      });
    });
  }

  void _removeMember(int index) {
    setState(() {
      _members.removeAt(index);
    });
  }

  Future<void> _handleNext() async {
    if (_members.isEmpty) {
      setState(() => _error = 'Please add at least one household member');
      return;
    }

    // Validate all members have names
    for (var i = 0; i < _members.length; i++) {
      if (_members[i]['name']?.toString().trim().isEmpty ?? true) {
        setState(() => _error = 'Please enter a name for all members');
        return;
      }
    }

    setState(() {
      _isLoading = true;
      _error = null;
    });

    final apiClient = Provider.of<ApiClient>(context, listen: false);
    final profileService = ProfileService(apiClient);
    final profileState = Provider.of<ProfileState>(context, listen: false);

    try {
      // Create household profile if doesn't exist
      if (!profileState.hasHouseholdProfile()) {
        await profileService.createHouseholdProfile();
      }

      // Create each family member
      for (var member in _members) {
        if (member['id'] == null) {
          // New member
          await profileService.createFamilyMember(
            name: member['name'],
            age: member['age'] ?? 30,
            allergens: [],
            dietaryRestrictions: [],
          );
        }
      }

      // Refetch full profile
      final profile = await profileService.getFullProfile();
      profileState.updateProfileData(profile);

      // Update onboarding status
      final status = await profileService.getOnboardingStatus();
      profileState.updateOnboardingStatus(status);

      // Save progress locally for offline resume
      final userId = profileState.userId;
      if (userId != null) {
        await OnboardingStorage.saveLastStep('HOUSEHOLD', userId);
      }

      if (mounted) {
        navigateToNextOnboardingStep(context, 'HOUSEHOLD');
      }
    } catch (e) {
      setState(() {
        _error = 'Failed to save: ${e.toString()}';
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Your Household'),
        actions: [
          TextButton(
            onPressed: () {
              // TODO: Save and exit
            },
            child: const Text('Save & Exit'),
          ),
        ],
      ),
      body: Column(
        children: [
          // Progress indicator
          LinearProgressIndicator(
            value: getOnboardingProgress('HOUSEHOLD'),
          ),
          
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    'Step ${getStepNumber('HOUSEHOLD')} of 8',
                    style: const TextStyle(
                      fontSize: 14,
                      color: Colors.grey,
                    ),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Who lives in your household?',
                    style: TextStyle(
                      fontSize: 24,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Add yourself and anyone else you cook for',
                    style: TextStyle(color: Colors.grey),
                  ),
                  const SizedBox(height: 32),
                  
                  // Member list
                  ListView.builder(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: _members.length,
                    itemBuilder: (context, index) {
                      return Card(
                        margin: const EdgeInsets.only(bottom: 16),
                        child: Padding(
                          padding: const EdgeInsets.all(16.0),
                          child: Column(
                            children: [
                              Row(
                                children: [
                                  Expanded(
                                    child: TextFormField(
                                      initialValue: _members[index]['name'],
                                      decoration: const InputDecoration(
                                        labelText: 'Name',
                                        border: OutlineInputBorder(),
                                      ),
                                      onChanged: (value) {
                                        _members[index]['name'] = value;
                                      },
                                    ),
                                  ),
                                  IconButton(
                                    icon: const Icon(Icons.delete),
                                    onPressed: () => _removeMember(index),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 16),
                              Row(
                                children: [
                                  Expanded(
                                    child: TextFormField(
                                      initialValue:
                                          _members[index]['age'].toString(),
                                      decoration: const InputDecoration(
                                        labelText: 'Age',
                                        border: OutlineInputBorder(),
                                      ),
                                      keyboardType: TextInputType.number,
                                      onChanged: (value) {
                                        _members[index]['age'] =
                                            int.tryParse(value) ?? 30;
                                      },
                                    ),
                                  ),
                                  const SizedBox(width: 16),
                                  Expanded(
                                    child: DropdownButtonFormField<String>(
                                      value: _members[index]['role'] ?? 'adult',
                                      decoration: const InputDecoration(
                                        labelText: 'Role',
                                        border: OutlineInputBorder(),
                                      ),
                                      items: const [
                                        DropdownMenuItem(
                                          value: 'adult',
                                          child: Text('Adult'),
                                        ),
                                        DropdownMenuItem(
                                          value: 'child',
                                          child: Text('Child'),
                                        ),
                                        DropdownMenuItem(
                                          value: 'senior',
                                          child: Text('Senior'),
                                        ),
                                      ],
                                      onChanged: (value) {
                                        setState(() {
                                          _members[index]['role'] = value;
                                        });
                                      },
                                    ),
                                  ),
                                ],
                              ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
                  
                  // Add member button
                  OutlinedButton.icon(
                    onPressed: _addMember,
                    icon: const Icon(Icons.add),
                    label: const Text('Add Member'),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                    ),
                  ),
                  
                  // Error message
                  if (_error != null) ...[
                    const SizedBox(height: 16),
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.red.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        _error!,
                        style: const TextStyle(color: Colors.red),
                        textAlign: TextAlign.center,
                      ),
                    ),
                  ],
                  
                  const SizedBox(height: 24),
                  
                  // Next button
                  ElevatedButton(
                    onPressed: _isLoading ? null : _handleNext,
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                    ),
                    child: _isLoading
                        ? const CircularProgressIndicator()
                        : const Text('Next: Allergies'),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
