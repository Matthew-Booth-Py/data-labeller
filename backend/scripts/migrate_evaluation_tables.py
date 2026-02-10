"""Migration script to add evaluation system tables to existing database.

This script adds the prompt_versions and evaluations tables to an existing
Unstructured Unlocked database without affecting existing data.

Usage:
    python scripts/migrate_evaluation_tables.py
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path to import from uu_backend
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from uu_backend.config import get_settings


def migrate_database():
    """Add evaluation system tables to existing database."""
    settings = get_settings()
    db_path = Path(settings.sqlite_database_path)
    
    if not db_path.exists():
        print(f"❌ Database not found at: {db_path}")
        print("   The database will be created automatically when you start the server.")
        return False
    
    print(f"📊 Migrating database: {db_path}")
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Check if tables already exist
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name IN ('prompt_versions', 'evaluations')
        """)
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        if 'prompt_versions' in existing_tables and 'evaluations' in existing_tables:
            print("✅ Evaluation tables already exist. No migration needed.")
            return True
        
        print("🔧 Creating evaluation system tables...")
        
        # Create prompt_versions table
        if 'prompt_versions' not in existing_tables:
            print("   Creating prompt_versions table...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS prompt_versions (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    document_type_id TEXT,
                    system_prompt TEXT NOT NULL,
                    user_prompt_template TEXT,
                    description TEXT,
                    is_active INTEGER NOT NULL DEFAULT 0,
                    created_by TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (document_type_id) REFERENCES document_types(id) ON DELETE CASCADE
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_prompt_versions_type
                ON prompt_versions(document_type_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_prompt_versions_active
                ON prompt_versions(is_active)
            """)
            
            print("   ✓ prompt_versions table created")
        
        # Create evaluations table
        if 'evaluations' not in existing_tables:
            print("   Creating evaluations table...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS evaluations (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    document_type_id TEXT NOT NULL,
                    prompt_version_id TEXT,
                    metrics TEXT NOT NULL,
                    extraction_time_ms INTEGER,
                    evaluated_by TEXT,
                    evaluated_at TEXT NOT NULL,
                    notes TEXT,
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
                    FOREIGN KEY (document_type_id) REFERENCES document_types(id) ON DELETE CASCADE,
                    FOREIGN KEY (prompt_version_id) REFERENCES prompt_versions(id) ON DELETE SET NULL
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_evaluations_document
                ON evaluations(document_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_evaluations_type
                ON evaluations(document_type_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_evaluations_prompt
                ON evaluations(prompt_version_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_evaluations_date
                ON evaluations(evaluated_at)
            """)
            
            print("   ✓ evaluations table created")
        
        conn.commit()
        
        # Verify tables were created
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name IN ('prompt_versions', 'evaluations')
        """)
        created_tables = [row[0] for row in cursor.fetchall()]
        
        if len(created_tables) == 2:
            print("\n✅ Migration completed successfully!")
            print(f"   - prompt_versions table: {'✓' if 'prompt_versions' in created_tables else '✗'}")
            print(f"   - evaluations table: {'✓' if 'evaluations' in created_tables else '✗'}")
            print("\n📝 Next steps:")
            print("   1. Restart your backend server")
            print("   2. Create your first prompt version: POST /api/evaluation/prompts")
            print("   3. Run an evaluation: POST /api/evaluation/run")
            print("   4. View results: GET /api/evaluation")
            return True
        else:
            print("❌ Migration failed - tables were not created")
            return False
            
    except Exception as e:
        print(f"❌ Migration failed with error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def check_prerequisites():
    """Check if prerequisites are met for migration."""
    settings = get_settings()
    db_path = Path(settings.sqlite_database_path)
    
    print("🔍 Checking prerequisites...")
    
    if not db_path.parent.exists():
        print(f"❌ Database directory does not exist: {db_path.parent}")
        print("   Creating directory...")
        db_path.parent.mkdir(parents=True, exist_ok=True)
        print("   ✓ Directory created")
    
    if not db_path.exists():
        print(f"⚠️  Database does not exist yet: {db_path}")
        print("   This is normal for a new installation.")
        print("   The database will be created when you start the server.")
        return False
    
    # Check if database is accessible
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        print(f"✓ Database is accessible")
        print(f"✓ Found {len(tables)} existing tables")
        
        # Check for required tables
        required_tables = ['document_types', 'labels', 'annotations']
        missing_tables = [t for t in required_tables if t not in tables]
        
        if missing_tables:
            print(f"⚠️  Missing required tables: {', '.join(missing_tables)}")
            print("   This might be a new or incomplete database.")
            print("   The tables will be created when you start the server.")
        
        return True
        
    except Exception as e:
        print(f"❌ Cannot access database: {e}")
        return False


def main():
    """Main migration function."""
    print("=" * 60)
    print("Unstructured Unlocked - Evaluation System Migration")
    print("=" * 60)
    print()
    
    # Check prerequisites
    if not check_prerequisites():
        print("\n⚠️  Prerequisites not met. Migration skipped.")
        print("   Start the server to initialize the database, then run this script.")
        return
    
    print()
    
    # Run migration
    success = migrate_database()
    
    print()
    print("=" * 60)
    
    if success:
        print("✅ Migration completed successfully!")
    else:
        print("❌ Migration failed. Check the error messages above.")
    
    print("=" * 60)


if __name__ == "__main__":
    main()
