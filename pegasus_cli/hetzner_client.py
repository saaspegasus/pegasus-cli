import hcloud
from hcloud.images import Image
from hcloud.locations import Location
from hcloud.server_types import ServerType
from hcloud.ssh_keys import SSHKey


class HetznerClient:
    def __init__(self, token: str):
        self.client = hcloud.Client(token=token)

    def validate_token(self) -> None:
        """Validate the token by making an API call. Raises on failure."""
        self.client.servers.get_all()

    def ensure_ssh_key(self, name: str, public_key: str) -> SSHKey:
        """Find an existing SSH key by content, or upload it.

        Matches by public key content (not name) to avoid duplicates.
        """
        existing_keys = self.client.ssh_keys.get_all()
        for key in existing_keys:
            if key.public_key.strip() == public_key.strip():
                return key

        return self.client.ssh_keys.create(name=name, public_key=public_key)

    def create_server(
        self,
        name: str,
        ssh_key: SSHKey,
        server_type: str = "cx22",
        image: str = "ubuntu-24.04",
        location: str = "nbg1",
    ):
        """Create a Hetzner server. Returns the create response (has .server and .action)."""
        return self.client.servers.create(
            name=name,
            server_type=ServerType(name=server_type),
            image=Image(name=image),
            location=Location(name=location),
            ssh_keys=[ssh_key],
        )
