# example.py

"""Sample Python file for Pydantree basic usage examples."""

import asyncio
import json
from typing import List, Dict, Optional, Union
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class User:
    """User data model."""
    id: int
    name: str
    email: str
    active: bool = True
    metadata: Dict[str, str] = field(default_factory=dict)


class UserManager:
    """Manage user operations."""
    
    def __init__(self, data_file: Optional[Path] = None):
        self.data_file = data_file or Path("users.json")
        self.users: List[User] = []
        self._cache = {}
    
    async def load_users(self) -> None:
        """Load users from data file."""
        if self.data_file.exists():
            with open(self.data_file) as f:
                data = json.load(f)
                self.users = [User(**user_data) for user_data in data]
    
    async def save_users(self) -> None:
        """Save users to data file."""
        data = []
        for user in self.users:
            user_dict = {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'active': user.active,
                'metadata': user.metadata
            }
            data.append(user_dict)
        
        with open(self.data_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def add_user(self, user: User) -> None:
        """Add a new user."""
        if self.find_user_by_id(user.id):
            raise ValueError(f"User with id {user.id} already exists")
        self.users.append(user)
    
    def find_user_by_id(self, user_id: int) -> Optional[User]:
        """Find user by ID."""
        if user_id in self._cache:
            return self._cache[user_id]
        
        for user in self.users:
            if user.id == user_id:
                self._cache[user_id] = user
                return user
        return None
    
    def find_users_by_status(self, active: bool = True) -> List[User]:
        """Find users by active status."""
        return [user for user in self.users if user.active == active]
    
    def update_user(self, user_id: int, **updates) -> bool:
        """Update user information."""
        user = self.find_user_by_id(user_id)
        if not user:
            return False
        
        for key, value in updates.items():
            if hasattr(user, key):
                setattr(user, key, value)
        
        # Invalidate cache
        if user_id in self._cache:
            del self._cache[user_id]
        
        return True
    
    def delete_user(self, user_id: int) -> bool:
        """Delete user by ID."""
        user = self.find_user_by_id(user_id)
        if user:
            self.users.remove(user)
            if user_id in self._cache:
                del self._cache[user_id]
            return True
        return False
    
    def get_statistics(self) -> Dict[str, Union[int, float]]:
        """Get user statistics."""
        if not self.users:
            return {"total": 0, "active": 0, "inactive": 0, "active_percentage": 0.0}
        
        total = len(self.users)
        active = len([u for u in self.users if u.active])
        inactive = total - active
        active_percentage = (active / total) * 100 if total > 0 else 0.0
        
        return {
            "total": total,
            "active": active,
            "inactive": inactive,
            "active_percentage": round(active_percentage, 2)
        }


def create_sample_users() -> List[User]:
    """Create sample user data."""
    return [
        User(1, "Alice Johnson", "alice@example.com", True, {"role": "admin"}),
        User(2, "Bob Smith", "bob@example.com", True, {"role": "user"}),
        User(3, "Charlie Brown", "charlie@example.com", False, {"role": "user"}),
        User(4, "Diana Prince", "diana@example.com", True, {"role": "moderator"}),
        User(5, "Eve Wilson", "eve@example.com", False, {"role": "user"})
    ]


async def main():
    """Main function demonstrating user management."""
    manager = UserManager(Path("sample_users.json"))
    
    # Add sample users
    for user in create_sample_users():
        try:
            manager.add_user(user)
            print(f"Added user: {user.name}")
        except ValueError as e:
            print(f"Error adding user: {e}")
    
    # Save to file
    await manager.save_users()
    print("Users saved to file")
    
    # Get statistics
    stats = manager.get_statistics()
    print(f"User statistics: {stats}")
    
    # Find active users
    active_users = manager.find_users_by_status(active=True)
    print(f"Active users: {[u.name for u in active_users]}")
    
    # Update a user
    if manager.update_user(1, email="alice.new@example.com"):
        print("Updated Alice's email")
    
    # Delete a user
    if manager.delete_user(5):
        print("Deleted Eve Wilson")
    
    print(f"Final user count: {len(manager.users)}")


if __name__ == "__main__":
    asyncio.run(main())
