"""Bootstrap a workspace from the current legacy file-based config."""

from __future__ import annotations

import argparse
import os

from config_loader import load_config
from workspace_repository import WorkspaceRepository


def parse_args():
    parser = argparse.ArgumentParser(description="Bootstrap a multitenant workspace from legacy config files.")
    parser.add_argument(
        "--workspace-name",
        default=os.environ.get("BOOTSTRAP_WORKSPACE_NAME", "Default Workspace"),
        help="Display name for the workspace to create or reuse.",
    )
    parser.add_argument(
        "--workspace-slug",
        default=os.environ.get("BOOTSTRAP_WORKSPACE_SLUG", "default"),
        help="Stable slug for the workspace.",
    )
    parser.add_argument(
        "--owner-email",
        default=os.environ.get("BOOTSTRAP_OWNER_EMAIL", "owner@example.com"),
        help="Owner email for the initial workspace membership.",
    )
    parser.add_argument(
        "--owner-name",
        default=os.environ.get("BOOTSTRAP_OWNER_NAME", ""),
        help="Display name for the owner account.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    config = load_config()
    repo = WorkspaceRepository(output_dir=config.get("output_dir", "/app/output"))
    try:
        workspace = repo.create_workspace(
            name=args.workspace_name,
            slug=args.workspace_slug,
            owner_email=args.owner_email,
            owner_name=args.owner_name,
        )
        repo.save_workspace_config(
            workspace_id=workspace["id"],
            config=config,
            preserve_existing_secrets=True,
        )
    finally:
        repo.close()

    print(
        f"Workspace bootstrapped: {workspace['name']} "
        f"({workspace['slug']}, {workspace['id']})"
    )


if __name__ == "__main__":
    main()
