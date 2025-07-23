#!/usr/bin/env python3
"""
Test database connection recovery
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.exc import OperationalError, DisconnectionError

def test_error_detection():
    """Test if we can properly detect database connection errors"""
    
    test_errors = [
        "SSL SYSCALL error: EOF detected",
        "psycopg2.OperationalError: SSL SYSCALL error: EOF detected",
        "Connection was forcibly closed",
        "Can't reconnect until invalid transaction is rolled back",
        "Some other random error"
    ]
    
    print("Testing database error detection:")
    print("=" * 50)
    
    for error_msg in test_errors:
        is_connection_error = (
            'ssl syscall error' in error_msg.lower() or 
            'eof detected' in error_msg.lower() or 
            'connection' in error_msg.lower() or
            'rolled back' in error_msg.lower()
        )
        
        status = "🔄 RECOVERABLE" if is_connection_error else "❌ NON-RECOVERABLE"
        print(f"{status}: {error_msg}")
    
    print("\n✅ Error detection test completed")

if __name__ == "__main__":
    test_error_detection()
