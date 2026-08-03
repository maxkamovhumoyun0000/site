import secrets
import string
import re
import logging
from typing import Dict, List, Tuple
from logging_config import get_logger

logger = get_logger(__name__)

# Security patterns to avoid
DANGEROUS_PATTERNS = [
    # Sequential patterns
    r'ABCDEF', r'123456', r'QWERTY', r'ASDFGH', r'ZXCVBN',
    # Repeated characters
    r'(.)\1{3,}',  # Same character repeated 3+ times
    # Keyboard adjacent
    r'QWER', r'WERE', r'ERTY', r'RTYU', r'TYUI', r'YUIO', r'UIOP',
    r'ASDF', r'SDFG', r'DFGH', r'FGHJ', r'GHJK', r'HJKL',
    r'ZXCV', r'XCVB', r'CVBN', r'VBNM',
    # Common patterns
    r'TEST', r'DEMO', r'STUD', r'TEACH', r'ADMIN',
]

# Compile patterns for efficiency
COMPILED_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in DANGEROUS_PATTERNS]

def generate_secure_login_id(login_type: int = 1, length: int = 5) -> str:
    """
    Generate cryptographically secure login ID
    
    Args:
        login_type: 1/2 for student, 3 for teacher
        length: number of random characters
    
    Returns:
        Secure login ID string
    """
    prefix = "Diamond-ST-" if login_type in (1, 2) else "Diamond-TR-"
    
    # Use secrets for cryptographically secure random generation
    # Mix of uppercase letters and digits
    charset = string.ascii_uppercase + string.digits
    suffix = ''.join(secrets.choice(charset) for _ in range(length))
    
    return f"{prefix}{suffix}"

def check_dangerous_patterns(login_id: str) -> List[str]:
    """
    Check if login ID contains dangerous patterns
    
    Args:
        login_id: Login ID to check
    
    Returns:
        List of dangerous patterns found
    """
    found_patterns = []
    
    for pattern in COMPILED_PATTERNS:
        if pattern.search(login_id):
            found_patterns.append(pattern.pattern)
    
    return found_patterns

def validate_login_id(login_id: str) -> Dict:
    """
    Comprehensive login ID validation
    
    Args:
        login_id: Login ID to validate
    
    Returns:
        Dictionary with validation results
    """
    result = {
        'valid': True,
        'warnings': [],
        'errors': [],
        'dangerous_patterns': [],
        'collision': False,
        'suggestions': []
    }
    
    # Basic format validation
    if not login_id:
        result['valid'] = False
        result['errors'].append("Login ID cannot be empty")
        return result
    
    if len(login_id) < 10:  # Diamond-X-XXXX minimum
        result['valid'] = False
        result['errors'].append("Login ID too short")
        return result
    
    # Check prefix
    if not (login_id.startswith('Diamond-ST-') or login_id.startswith('Diamond-TR-')):
        result['warnings'].append("Unusual prefix detected")
    
    # Check dangerous patterns
    dangerous = check_dangerous_patterns(login_id)
    if dangerous:
        result['valid'] = False
        result['dangerous_patterns'] = dangerous
        result['errors'].append("Contains dangerous patterns")
    
    # Check suffix length and format
    parts = login_id.split('-')
    if len(parts) != 3:
        result['valid'] = False
        result['errors'].append("Invalid format")
        return result
    
    suffix = parts[2]
    if len(suffix) < 4:
        result['valid'] = False
        result['errors'].append("Suffix too short")
    elif len(suffix) > 8:
        result['warnings'].append("Suffix very long")
    
    # Check if suffix contains only valid characters
    if not re.match(r'^[A-Z0-9]+$', suffix):
        result['valid'] = False
        result['errors'].append("Suffix contains invalid characters")
    
    # Generate suggestions if invalid
    if not result['valid']:
        login_type = 2 if 'ST' in login_id else 3
        for i in range(3):
            suggestion = generate_secure_login_id(login_type, 5)
            validation = validate_login_id(suggestion)
            if validation['valid']:
                result['suggestions'].append(suggestion)
    
    return result

def is_login_id_safe(login_id: str) -> bool:
    """
    Quick safety check for login ID
    
    Args:
        login_id: Login ID to check
    
    Returns:
        True if safe, False otherwise
    """
    validation = validate_login_id(login_id)
    return validation['valid']

def get_login_id_strength(login_id: str) -> str:
    """
    Get strength rating for login ID
    
    Args:
        login_id: Login ID to evaluate
    
    Returns:
        Strength rating: 'weak', 'medium', 'strong'
    """
    validation = validate_login_id(login_id)
    
    if not validation['valid']:
        return 'weak'
    
    if validation['warnings']:
        return 'medium'
    
    return 'strong'

def generate_batch_login_ids(login_type: int, count: int, length: int = 5) -> List[str]:
    """
    Generate multiple safe login IDs
    
    Args:
        login_type: 1/2 for student, 3 for teacher
        count: Number of IDs to generate
        length: Length of random suffix
    
    Returns:
        List of safe login IDs
    """
    ids = []
    attempts = 0
    max_attempts = count * 10  # Prevent infinite loops
    
    while len(ids) < count and attempts < max_attempts:
        candidate = generate_secure_login_id(login_type, length)
        validation = validate_login_id(candidate)
        
        if validation['valid']:
            # Check for duplicates in current batch
            if candidate not in ids:
                ids.append(candidate)
                logger.debug(f"Generated safe login ID: {candidate}")
        
        attempts += 1
    
    if len(ids) < count:
        logger.warning(f"Could only generate {len(ids)} out of {count} safe IDs")
    
    logger.info(f"Generated {len(ids)} safe login IDs for type {login_type}")
    return ids

# Security monitoring
def audit_login_id(login_id: str, context: str = "") -> Dict:
    """
    Audit login ID for security purposes
    
    Args:
        login_id: Login ID to audit
        context: Additional context (e.g., user creation, manual entry)
    
    Returns:
        Audit results
    """
    validation = validate_login_id(login_id)
    
    audit_result = {
        'login_id': login_id,
        'context': context,
        'timestamp': secrets.token_hex(8),
        'validation': validation,
        'security_level': get_login_id_strength(login_id),
        'requires_attention': not validation['valid'] or bool(validation['warnings'])
    }
    
    # Log security events
    if not validation['valid']:
        logger.warning(f"Unsafe login ID detected: {login_id} - {validation['errors']}")
    
    if validation['dangerous_patterns']:
        logger.critical(f"Dangerous patterns in login ID: {login_id} - {validation['dangerous_patterns']}")
    
    return audit_result
