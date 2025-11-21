from fastapi import APIRouter
from chat_db.databse import get_all_records 

 
router = APIRouter()  # FIX: Added parentheses to instantiate
@router.get("/history")  # FIX: Corrected spelling from /hisotry to /history
def history():
     """Get all chat history records."""
     records = get_all_records()  # FIX: Actually call the function
     
     # Format the response
     formatted_records = []
     for record in records:
         formatted_records.append({
             "id": record[0],
             "role": record[1],
             "output": record[2],
             "timestamp": record[3]
         })
     
     return {
         "total": len(formatted_records),
         "records": formatted_records
     }