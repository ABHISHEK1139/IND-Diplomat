from dip.ecosystem.sdk.core import hookimpl, DIPExpertPlugin

@hookimpl
def register_expert():
    """
    Registers a 3rd party Climate Intelligence Expert into the reasoning council.
    """
    return DIPExpertPlugin(
        role_name="Climate Intelligence Analyst",
        expertise="Global Warming, Resource Scarcity, and Extreme Weather Events"
    )
