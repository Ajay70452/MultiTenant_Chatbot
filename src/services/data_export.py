import os
import json
import csv
from src.models.models import Conversation # Import the Conversation model for type hinting

def simple_data_exporter(conversation: Conversation):
    """
    Prints and saves the final lead data to a CSV file for manual follow-up.
    """
    
    # Data to be exported, with graceful handling of missing state keys
    lead_data = {
        'Client ID': str(conversation.client_id),
        'Conversation ID': str(conversation.conversation_id),
        'Name': conversation.conversation_state.get('name', 'N/A'),
        'Phone': conversation.conversation_state.get('phone', 'N/A'),
        'Email': conversation.conversation_state.get('email', 'N/A'),
        'Service': conversation.conversation_state.get('service', 'N/A'),
        'Finalized At': conversation.finalized_at.isoformat() if conversation.finalized_at else 'N/A'
    }
    
    # 1. Log to console for immediate visibility (simulating an internal notification)
    print("\n*** LEAD FINALIZED - MANUAL ACTION REQUIRED ***")
    print(json.dumps(lead_data, indent=4))
    print("*********************************************\n")
    
    # 2. Write to a local CSV file (simulating a Google Sheet or CRM export)
    # This file will be created in the root directory of your project.
    file_path = "finalized_leads.csv"
    # os.path.isfile() checks if a file exists at the given path
    file_exists = os.path.isfile(file_path)
    
    try:
        # 'a' stands for append mode, which adds a new row without overwriting the file
        with open(file_path, 'a', newline='', encoding='utf-8') as csvfile:
            fieldnames = lead_data.keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            # Write the header row only if the file is being created for the first time
            if not file_exists:
                writer.writeheader()
                
            writer.writerow(lead_data)
        
        print(f"✅ Lead data successfully appended to {file_path}")
    except Exception as e:
        print(f"❌ FAILED to write lead data to CSV. Reason: {e}")
    
    return True