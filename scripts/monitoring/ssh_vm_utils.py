import subprocess
import os
import sys
import logging
from paramiko.ssh_exception import AuthenticationException
from paramiko import SSHClient, AutoAddPolicy, RSAKey, SSHException
from scp import SCPClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def vm_reachable_decorator(func):
    def wrapper(ssh_host, *args, **kwargs):
        try:
            response = subprocess.run(['ping', '-n', '1', ssh_host],
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
            if response.returncode == 0:
                logger.info(f"VM {ssh_host} is reachable. Proceeding with the operation.")
                return func(ssh_host, *args, **kwargs)
            else:
                logger.error(f"VM {ssh_host} is not reachable. Aborting the operation.")
                return False
        except Exception as e:
            logger.error(f"Error while trying to ping VM: {e}")
            return False
    return wrapper


def create_ssh_key(ssh_key_path):
    ssh_dir = os.path.dirname(ssh_key_path)
    if not os.path.exists(ssh_dir):
        logger.info(f"Creating directory {ssh_dir}")
        os.makedirs(ssh_dir, exist_ok=True)

    if not os.path.exists(ssh_key_path):
        logger.info("Generating SSH key...")
        try:
            subprocess.run(["ssh-keygen", "-t", "rsa", "-b", "2048", "-N", "", "-f", ssh_key_path], check=True)
            logger.info(f"SSH key generated at {ssh_key_path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to generate SSH key: {e}")
            sys.exit(1)
    else:
        logger.info(f"SSH key already exists at {ssh_key_path}")


def copy_public_key_to_vm(ssh_host, ssh_port, ssh_user, local_public_key_path, ssh_key_filepath):
    try:
        with SSHClient() as ssh_client:
            ssh_client.set_missing_host_key_policy(AutoAddPolicy())

            try:
                ssh_key = RSAKey.from_private_key_file(ssh_key_filepath)
                ssh_client.connect(hostname=ssh_host, port=ssh_port, username=ssh_user, pkey=ssh_key)

                with open(local_public_key_path, 'r') as local_public_key_file:
                    public_key = local_public_key_file.read()

                ssh_client.exec_command(f'echo "{public_key}" >> ~/.ssh/authorized_keys')

                return True
            except AuthenticationException as key_auth_error:
                logger.warning(f"SSH key-based authentication failed: {key_auth_error}")

            ssh_password = input("Enter the SSH password for the VM: ")

            ssh_client.connect(hostname=ssh_host, port=ssh_port, username=ssh_user, password=ssh_password)

            with open(local_public_key_path, 'r') as local_public_key_file:
                public_key = local_public_key_file.read()

            ssh_client.exec_command(f'echo "{public_key}" >> ~/.ssh/authorized_keys')

            return True

    except SSHException as e:
        logger.error(f"SSH error while copying public key to VM: {e}")
    except Exception as e:
        logger.error(f"An error occurred while connecting to VM: {e}")

    return False


def transfer_script(ssh_host,
                    ssh_key_filepath,
                    ssh_port,
                    ssh_user,
                    local_status_script_path,
                    remote_script_path,
                    script_filename):
    try:
        ssh_key = RSAKey.from_private_key_file(ssh_key_filepath)
        with SSHClient() as ssh_client:
            ssh_client.set_missing_host_key_policy(AutoAddPolicy())
            ssh_client.connect(hostname=ssh_host, port=ssh_port, username=ssh_user, pkey=ssh_key)
            with SCPClient(ssh_client.get_transport()) as scp_client:
                scp_client.put(local_status_script_path, remote_script_path)

                ssh_client.exec_command(f'chmod +x {script_filename}')
        return True
    except SSHException as e:
        logger.error(f"SSH error while transferring script: {e}")
        return False
