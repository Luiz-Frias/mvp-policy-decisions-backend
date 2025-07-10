#!/usr/bin/env python3
"""Fix missing BaseModelConfig imports in auto-generated models."""

import re
from pathlib import Path


def fix_missing_imports(file_path: Path) -> bool:
    """Fix missing BaseModelConfig import in a file."""
    try:
        with open(file_path, 'r') as f:
            content = f.read()

        # Check if file uses BaseModelConfig but doesn't import it
        has_basemodel_usage = 'BaseModelConfig' in content
        has_basemodel_import = 'from' in content and 'BaseModelConfig' in content and any('BaseModelConfig' in line for line in content.split('\n') if line.strip().startswith('from'))

        if has_basemodel_usage and not has_basemodel_import:
            lines = content.split('\n')

            # Determine the correct import path based on file location
            file_parts = str(file_path).split('/')
            if 'core' in file_parts:
                if 'auth' in file_parts:
                    import_line = 'from ...models.base import BaseModelConfig'
                else:
                    import_line = 'from ..models.base import BaseModelConfig'
            elif 'websocket' in file_parts:
                if 'handlers' in file_parts:
                    import_line = 'from ...models.base import BaseModelConfig'
                else:
                    import_line = 'from ..models.base import BaseModelConfig'
            elif 'api' in file_parts:
                if 'admin' in file_parts:
                    import_line = 'from ....models.base import BaseModelConfig'
                else:
                    import_line = 'from ...models.base import BaseModelConfig'
            elif 'services' in file_parts:
                if 'admin' in file_parts or 'rating' in file_parts:
                    import_line = 'from ...models.base import BaseModelConfig'
                else:
                    import_line = 'from ..models.base import BaseModelConfig'
            elif 'compliance' in file_parts:
                import_line = 'from ..models.base import BaseModelConfig'
            else:
                import_line = 'from .models.base import BaseModelConfig'

            # Find where to insert the import
            insert_idx = 0
            last_import_idx = -1

            for i, line in enumerate(lines):
                if line.strip().startswith(('import ', 'from ')):
                    last_import_idx = i
                elif line.strip() and not line.strip().startswith('#') and last_import_idx != -1:
                    insert_idx = last_import_idx + 1
                    break

            # Check if we need Field import too
            needs_field = 'Field(' in content and 'from pydantic import' not in content

            if needs_field:
                # Check if there's already a pydantic import to extend
                pydantic_idx = -1
                for i, line in enumerate(lines):
                    if 'from pydantic import' in line:
                        pydantic_idx = i
                        break

                if pydantic_idx != -1:
                    # Add Field to existing import
                    lines[pydantic_idx] = lines[pydantic_idx].rstrip(') ')
                    if not lines[pydantic_idx].endswith(','):
                        lines[pydantic_idx] += ', Field'
                    else:
                        lines[pydantic_idx] += ' Field'
                else:
                    # Add new pydantic import
                    lines.insert(insert_idx, 'from pydantic import Field')
                    insert_idx += 1

            # Insert BaseModelConfig import
            lines.insert(insert_idx, import_line)

            # Write back
            with open(file_path, 'w') as f:
                f.write('\n'.join(lines))

            print(f"Fixed: {file_path}")
            return True

    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
        return False


def main():
    """Fix all files with missing imports."""
    files_to_fix = [
        "src/pd_prime_demo/compliance/evidence_collector.py",
        "src/pd_prime_demo/compliance/processing_integrity.py",
        "src/pd_prime_demo/services/transaction_helpers.py",
        "src/pd_prime_demo/services/quote_wizard.py",
        "src/pd_prime_demo/services/rating/business_rules.py",
        "src/pd_prime_demo/services/rating/performance.py",
        "src/pd_prime_demo/services/rating/territory_management.py",
        "src/pd_prime_demo/services/rating/rating_engine.py",
        "src/pd_prime_demo/services/rating/state_rules.py",
        "src/pd_prime_demo/services/rating/performance_optimizer.py",
        "src/pd_prime_demo/services/rating/cache_strategy.py",
        "src/pd_prime_demo/services/quote_service.py",
        "src/pd_prime_demo/services/admin/system_settings_service.py",
        "src/pd_prime_demo/services/admin/activity_logger.py",
        "src/pd_prime_demo/services/admin/admin_user_service.py",
        "src/pd_prime_demo/api/response_patterns.py",
        "src/pd_prime_demo/api/v1/mfa.py",
        "src/pd_prime_demo/api/v1/compliance.py",
        "src/pd_prime_demo/api/v1/admin/rate_management.py",
        "src/pd_prime_demo/api/v1/admin/pricing_controls.py",
        "src/pd_prime_demo/api/v1/admin/websocket_admin.py",
        "src/pd_prime_demo/api/v1/admin/sso_management.py",
        "src/pd_prime_demo/api/v1/admin/quotes.py",
        "src/pd_prime_demo/api/v1/quotes.py",
        "src/pd_prime_demo/core/query_optimizer.py",
        "src/pd_prime_demo/core/admin_query_optimizer.py",
        "src/pd_prime_demo/core/performance_monitor.py",
        "src/pd_prime_demo/core/auth/oauth2/api_keys.py",
        "src/pd_prime_demo/core/auth/oauth2/server.py",
        "src/pd_prime_demo/core/auth/oauth2/client_certificates.py",
        "src/pd_prime_demo/core/auth/mfa/webauthn.py",
        "src/pd_prime_demo/core/auth/mfa/risk_engine.py",
        "src/pd_prime_demo/core/performance_cache.py",
        "src/pd_prime_demo/websocket/message_models.py",
        "src/pd_prime_demo/websocket/permissions.py",
        "src/pd_prime_demo/websocket/handlers/analytics.py",
        "src/pd_prime_demo/websocket/handlers/admin_dashboard.py",
        "src/pd_prime_demo/websocket/handlers/notifications.py",
        "src/pd_prime_demo/websocket/handlers/quotes.py",
        "src/pd_prime_demo/websocket/manager.py",
        "src/pd_prime_demo/websocket/monitoring.py",
    ]

    fixed = 0
    for file_path in files_to_fix:
        if fix_missing_imports(Path(file_path)):
            fixed += 1

    print(f"\nFixed {fixed} files with missing BaseModelConfig imports")


if __name__ == '__main__':
    main()
