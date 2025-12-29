"""
In-memory storage for MVP-0 (fastest implementation)
Stores config, inventory, and history in memory
"""
from typing import Dict, List, Optional
from datetime import datetime
import uuid

from app.models.config import AppConfiguration
from app.models.inventory import InventoryItem, InventoryItemCreate, InventoryItemUpdate
from app.models.history import RecipeHistoryCreate, RecipeHistoryResponse


class InMemoryStorage:
    """Singleton in-memory storage for MVP"""
    
    def __init__(self):
        # Configuration storage
        self._config: Optional[AppConfiguration] = None
        
        # Inventory storage: inventory_id -> InventoryItem
        self._inventory: Dict[str, InventoryItem] = {}
        
        # History storage: history_id -> dict
        self._history: List[Dict] = []
        
        # Plan storage for debugging/repeatability (optional)
        self._plans: Dict[str, Dict] = {}
    
    # Configuration methods
    def get_config(self) -> AppConfiguration:
        """Get current configuration, return default if not set"""
        if self._config is None:
            self._config = AppConfiguration()
        return self._config
    
    def set_config(self, config: AppConfiguration) -> AppConfiguration:
        """Set/update configuration"""
        self._config = config
        return self._config
    
    # Inventory methods
    def list_inventory(self) -> List[InventoryItem]:
        """List all inventory items"""
        return list(self._inventory.values())
    
    def get_inventory_item(self, inventory_id: str) -> Optional[InventoryItem]:
        """Get single inventory item"""
        return self._inventory.get(inventory_id)
    
    def create_inventory_item(self, item: InventoryItemCreate) -> InventoryItem:
        """Create new inventory item"""
        inventory_id = f"inv_{uuid.uuid4().hex[:12]}"
        new_item = InventoryItem(
            inventory_id=inventory_id,
            **item.model_dump()
        )
        if new_item.added_date is None:
            new_item.added_date = datetime.utcnow()
        self._inventory[inventory_id] = new_item
        return new_item
    
    def update_inventory_item(self, inventory_id: str, updates: InventoryItemUpdate) -> Optional[InventoryItem]:
        """Update existing inventory item"""
        item = self._inventory.get(inventory_id)
        if item is None:
            return None
        
        # Apply updates
        update_data = updates.model_dump(exclude_unset=True)
        updated_item = item.model_copy(update=update_data)
        self._inventory[inventory_id] = updated_item
        return updated_item
    
    def delete_inventory_item(self, inventory_id: str) -> bool:
        """Delete inventory item, return True if existed"""
        return self._inventory.pop(inventory_id, None) is not None
    
    # History methods
    def create_history_entry(self, entry: RecipeHistoryCreate) -> RecipeHistoryResponse:
        """Record a cooked recipe in history"""
        history_id = f"hist_{uuid.uuid4().hex[:12]}"
        cooked_at = datetime.utcnow()
        
        history_entry = {
            "history_id": history_id,
            "cooked_at": cooked_at,
            **entry.model_dump()
        }
        self._history.append(history_entry)
        
        return RecipeHistoryResponse(
            history_id=history_id,
            recipe_id=entry.recipe_id,
            cooked_at=cooked_at
        )
    
    def get_recent_history(self, limit: int = 50) -> List[Dict]:
        """Get recent history entries for variety calculation"""
        return sorted(self._history, key=lambda x: x["cooked_at"], reverse=True)[:limit]
    
    # Plan storage (optional, for debugging)
    def store_plan(self, plan_id: str, plan_data: Dict) -> None:
        """Store a generated plan for debugging/repeatability"""
        self._plans[plan_id] = {
            "plan_id": plan_id,
            "created_at": datetime.utcnow(),
            "data": plan_data
        }
    
    def get_plan(self, plan_id: str) -> Optional[Dict]:
        """Retrieve a stored plan"""
        return self._plans.get(plan_id)


# Global storage instance
storage = InMemoryStorage()


def get_storage() -> InMemoryStorage:
    """Get the global storage instance"""
    return storage
