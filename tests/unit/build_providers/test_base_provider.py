# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright (C) 2018 Canonical Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import contextlib
import os
from unittest.mock import call, Mock

from testtools.matchers import Equals, EndsWith, DirExists, Not

from . import BaseProviderBaseTest, ProviderImpl
from snapcraft.internal.build_providers import errors


class BaseProviderTest(BaseProviderBaseTest):
    def test_initialize(self):
        provider = ProviderImpl(project=self.project, echoer=self.echoer_mock)

        self.assertThat(provider.project, Equals(self.project))
        self.assertThat(provider.instance_name, Equals(self.instance_name))
        self.assertThat(
            provider.provider_project_dir,
            EndsWith(
                os.path.join("snapcraft", "projects", "project-name", "stub-provider")
            ),
        )
        self.assertThat(
            provider.snap_filename,
            Equals("project-name_{}.snap".format(self.project.deb_arch)),
        )

    def test_context(self):
        with ProviderImpl(project=self.project, echoer=self.echoer_mock) as provider:
            provider.shell()
            fake_provider = provider

        fake_provider.create_mock.assert_called_once_with("create")
        fake_provider.destroy_mock.assert_called_once_with("destroy")

    def test_context_fails_create(self):
        create_mock = Mock()
        destroy_mock = Mock()

        class BadProviderImpl(ProviderImpl):
            def create(self):
                super().create()
                create_mock("create bad")
                raise errors.ProviderBaseError()

            def destroy(self):
                super().destroy()
                destroy_mock("destroy bad")

        with contextlib.suppress(errors.ProviderBaseError):
            with BadProviderImpl(project=self.project, echoer=self.echoer_mock):
                pass

        create_mock.assert_called_once_with("create bad")
        destroy_mock.assert_called_once_with("destroy bad")

    def test_initialize_snap_filename_with_version(self):
        self.project.info.version = "test-version"

        provider = ProviderImpl(project=self.project, echoer=self.echoer_mock)

        self.assertThat(
            provider.snap_filename,
            Equals("project-name_test-version_{}.snap".format(self.project.deb_arch)),
        )

    def test_launch_instance(self):
        provider = ProviderImpl(project=self.project, echoer=self.echoer_mock)
        provider.start_mock.side_effect = errors.ProviderInstanceNotFoundError(
            instance_name=self.instance_name
        )
        provider.launch_instance()

        provider.launch_mock.assert_any_call()
        provider.start_mock.assert_any_call()
        provider.run_mock.assert_called_once_with(["snapcraft", "refresh"])

        self.assertThat(provider.provider_project_dir, DirExists())

    def test_start_instance(self):
        provider = ProviderImpl(project=self.project, echoer=self.echoer_mock)

        provider.launch_instance()

        provider.launch_mock.assert_not_called()
        provider.start_mock.assert_any_call()
        provider.run_mock.assert_not_called()

        # Given the way we constructe this test, this directory should not exist
        # TODO add robustness to start. (LP: #1792242)
        self.assertThat(provider.provider_project_dir, Not(DirExists()))


class BaseProviderProvisionSnapcraftTest(BaseProviderBaseTest):
    def test_setup_snapcraft(self):
        provider = ProviderImpl(project=self.project, echoer=self.echoer_mock)
        provider._setup_snapcraft()

        self.snap_injector_mock.assert_called_once_with(
            snap_dir=provider._SNAPS_MOUNTPOINT,
            registry_filepath=os.path.join(
                provider.provider_project_dir, "snap-registry.yaml"
            ),
            snap_arch=self.project.deb_arch,
            runner=provider._run,
            snap_dir_mounter=provider._mount_snaps_directory,
            snap_dir_unmounter=provider._unmount_snaps_directory,
            file_pusher=provider._push_file,
        )
        self.snap_injector_mock().add.assert_has_calls(
            [
                call(snap_name="core"),
                call(snap_name="snapcraft"),
                call(snap_name="core16"),
            ]
        )
        self.assertThat(self.snap_injector_mock().add.call_count, Equals(3))
        self.snap_injector_mock().apply.assert_called_once_with()

    def test_ephemeral_setup_snapcraft(self):
        provider = ProviderImpl(
            project=self.project, echoer=self.echoer_mock, is_ephemeral=True
        )
        provider._setup_snapcraft()

        self.snap_injector_mock.assert_called_once_with(
            snap_dir=provider._SNAPS_MOUNTPOINT,
            registry_filepath=os.path.join(
                provider.provider_project_dir, "snap-registry.yaml"
            ),
            snap_arch=self.project.deb_arch,
            runner=provider._run,
            snap_dir_mounter=provider._mount_snaps_directory,
            snap_dir_unmounter=provider._unmount_snaps_directory,
            file_pusher=provider._push_file,
        )
        self.snap_injector_mock().add.assert_has_calls(
            [
                call(snap_name="core"),
                call(snap_name="snapcraft"),
                call(snap_name="core16"),
            ]
        )
        self.assertThat(self.snap_injector_mock().add.call_count, Equals(3))
        self.snap_injector_mock().apply.assert_called_once_with()

    def test_setup_snapcraft_for_classic_build(self):
        self.project.info.base = "core18"
        self.project.info.confinement = "classic"

        provider = ProviderImpl(project=self.project, echoer=self.echoer_mock)
        provider._setup_snapcraft()

        self.snap_injector_mock().add.assert_has_calls(
            [
                call(snap_name="core"),
                call(snap_name="snapcraft"),
                call(snap_name="core18"),
            ]
        )
        self.assertThat(self.snap_injector_mock().add.call_count, Equals(3))
        self.snap_injector_mock().apply.assert_called_once_with()
