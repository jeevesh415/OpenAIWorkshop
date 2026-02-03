import os
from typing import Optional

try:  # Optional dependency; backend should still run without it
    from azure.monitor.opentelemetry import configure_azure_monitor
    from agent_framework.observability import setup_observability
    from opentelemetry.sdk.resources import Resource
except Exception:  # pragma: no cover - best-effort import
    configure_azure_monitor = None  # type: ignore[assignment]
    setup_observability = None  # type: ignore[assignment]
    Resource = None  # type: ignore[assignment]


def setup_telemetry() -> None:
    """Configure Azure Monitor for Agent Framework to show traces in Foundry.

    This follows the exact pattern from the Microsoft blog post:
    "Agentic Applications on Azure Container Apps with Microsoft Foundry"
    """
    
    print("🔍 DEBUG: setup_telemetry() called")
    
    connection_string: Optional[str] = os.getenv("APPLICATION_INSIGHTS_CONNECTION_STRING")
    print(f"🔍 DEBUG: Application Insights connection string exists: {bool(connection_string)}")
    
    if not connection_string:
        print("❌ DEBUG: No APPLICATION_INSIGHTS_CONNECTION_STRING found, skipping telemetry")
        return
        
    if configure_azure_monitor is None:
        print("❌ DEBUG: configure_azure_monitor not available, skipping telemetry")
        return

    try:
        print("🚀 DEBUG: Calling configure_azure_monitor...")
        # Configure Azure Monitor first (exact pattern from blog)
        configure_azure_monitor(
            resource=Resource.create({"service.name": "contoso-agent-backend"}) if Resource else None,
            connection_string=connection_string,
            disable_offline_storage=True,  # Disable storage to avoid the NoneType error
        )
        print("✅ DEBUG: configure_azure_monitor completed")
        
        # Enable Microsoft Agent Framework telemetry (correct function!)
        if setup_observability is not None:
            print("🚀 DEBUG: Calling setup_observability...")
            setup_observability(enable_sensitive_data=False)
            print("✅ DEBUG: setup_observability completed")
        else:
            print("❌ DEBUG: setup_observability not available")
            
        print("🎉 DEBUG: Telemetry setup complete!")
        
    except Exception as e:
        print(f"❌ DEBUG: Telemetry setup failed with error: {e}")
        import traceback
        traceback.print_exc()
            
    except Exception:
        # Telemetry should never break the app; swallow configuration errors.
        return