import sqlalchemy
from sqlalchemy import text
from backend.database import engine

def migrate():
    with engine.connect() as conn:
        # Check and add import_batch_id to transactions
        try:
            conn.execute(text("ALTER TABLE transactions ADD COLUMN IF NOT EXISTS import_batch_id VARCHAR"))
            print("Added import_batch_id to transactions")
        except Exception as e:
            print("Error on transactions.import_batch_id:", e)

        # Check and add import_batch_id to recovery_workflows
        try:
            conn.execute(text("ALTER TABLE recovery_workflows ADD COLUMN IF NOT EXISTS import_batch_id VARCHAR"))
            print("Added import_batch_id to recovery_workflows")
        except Exception as e:
            print("Error on recovery_workflows.import_batch_id:", e)

        # Check and add transaction_id to recovery_workflows
        try:
            conn.execute(text("ALTER TABLE recovery_workflows ADD COLUMN IF NOT EXISTS transaction_id VARCHAR"))
            print("Added transaction_id to recovery_workflows")
        except Exception as e:
            print("Error on recovery_workflows.transaction_id:", e)

        # Add foreign key constraint safely if not exists
        try:
            # We check if constraint exists
            result = conn.execute(text("SELECT constraint_name FROM information_schema.table_constraints WHERE table_name='recovery_workflows' AND constraint_type='FOREIGN KEY' AND constraint_name='fk_recovery_workflows_transaction_id'"))
            if not result.fetchone():
                conn.execute(text("ALTER TABLE recovery_workflows ADD CONSTRAINT fk_recovery_workflows_transaction_id FOREIGN KEY (transaction_id) REFERENCES transactions (transaction_id) ON DELETE CASCADE"))
                print("Added foreign key to recovery_workflows")
            else:
                print("Foreign key already exists")
        except Exception as e:
            print("Error on foreign key:", e)

        conn.commit()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
