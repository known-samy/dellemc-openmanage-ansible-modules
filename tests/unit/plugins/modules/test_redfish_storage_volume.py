# -*- coding: utf-8 -*-

#
# Dell OpenManage Ansible Modules
# Version 7.0.0
# Copyright (C) 2020-2022 Dell Inc. or its subsidiaries. All Rights Reserved.

# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
#

from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

import pytest
import json
from ansible_collections.dellemc.openmanage.plugins.modules import redfish_storage_volume
from ansible_collections.dellemc.openmanage.tests.unit.plugins.modules.common import FakeAnsibleModule
from ansible.module_utils.six.moves.urllib.error import URLError, HTTPError
from ansible.module_utils.urls import ConnectionError, SSLValidationError
from io import StringIO
from ansible.module_utils._text import to_text

MODULE_PATH = 'ansible_collections.dellemc.openmanage.plugins.modules.'


@pytest.fixture
def redfish_connection_mock_for_storage_volume(mocker, redfish_response_mock):
    connection_class_mock = mocker.patch(MODULE_PATH + 'redfish_storage_volume.Redfish')
    redfish_connection_mock_obj = connection_class_mock.return_value.__enter__.return_value
    redfish_connection_mock_obj.invoke_request.return_value = redfish_response_mock
    return redfish_connection_mock_obj


class TestStorageVolume(FakeAnsibleModule):
    module = redfish_storage_volume

    @pytest.fixture
    def storage_volume_base_uri(self):
        self.module.storage_collection_map.update({"storage_base_uri": "/redfish/v1/Systems/System.Embedded.1/Storage"})

    arg_list1 = [{"state": "present"}, {"state": "present", "volume_id": "volume_id"},
                 {"state": "absent", "volume_id": "volume_id"},
                 {"command": "initialize", "volume_id": "volume_id"},
                 {"state": "present", "volume_type": "NonRedundant",
                  "name": "name", "controller_id": "controller_id",
                  "drives": ["drive1"],
                  "block_size_bytes": 123,
                  "capacity_bytes": "1234567",
                  "optimum_io_size_bytes": "1024",
                  "encryption_types": "NativeDriveEncryption",
                  "encrypted": False,
                  "volume_id": "volume_id", "oem": {"Dell": "DellAttributes"},
                  "initialize_type": "Slow",
                  "reboot_server": True
                  }]

    @pytest.mark.parametrize("param", arg_list1)
    def test_redfish_storage_volume_main_success_case_01(self, mocker, redfish_default_args, module_mock,
                                                         redfish_connection_mock_for_storage_volume, param,
                                                         storage_volume_base_uri):
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.validate_inputs')
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.fetch_storage_resource')
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.configure_raid_operation',
                     return_value={"msg": "Successfully submitted volume task.",
                                   "task_uri": "task_uri",
                                   "task_id": 1234})
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.check_apply_time_supported_and_reboot_required',
                     return_value=True)
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.perform_reboot')
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.check_job_tracking_required',
                     return_value=False)
        redfish_default_args.update(param)
        result = self._run_module(redfish_default_args)
        assert result["changed"] is True
        assert result['msg'] == "Successfully submitted volume task."
        assert result["task"]["id"] == 1234

    arg_list2 = [
        {"state": "absent"},
        {"command": "initialize"}, {}]

    @pytest.mark.parametrize("param", arg_list2)
    def test_redfish_storage_volume_main_failure_case_01(self, param, redfish_default_args, module_mock):
        """required parameter is not passed along with specified report_type"""
        redfish_default_args.update(param)
        result = self._run_module_with_fail_json(redfish_default_args)
        assert 'msg' in result
        assert "task" not in result
        assert result['failed'] is True

    @pytest.mark.parametrize("exc_type",
                             [URLError, HTTPError, SSLValidationError, ConnectionError, TypeError, ValueError])
    def test_redfish_storage_volume_main_exception_handling_case(self, exc_type, mocker, redfish_default_args,
                                                                 redfish_connection_mock_for_storage_volume,
                                                                 redfish_response_mock):
        redfish_default_args.update({"state": "present"})
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.validate_inputs')
        redfish_response_mock.status_code = 400
        redfish_response_mock.success = False
        json_str = to_text(json.dumps({"data": "out"}))

        if exc_type not in [HTTPError, SSLValidationError]:
            mocker.patch(MODULE_PATH + 'redfish_storage_volume.configure_raid_operation',
                         side_effect=exc_type('test'))
        else:
            mocker.patch(MODULE_PATH + 'redfish_storage_volume.configure_raid_operation',
                         side_effect=exc_type('https://testhost.com', 400, 'http error message',
                                              {"accept-type": "application/json"}, StringIO(json_str)))
        result = self._run_module(redfish_default_args)
        assert 'task' not in result
        assert 'msg' in result
        if exc_type != URLError:
            assert result['failed'] is True
        else:
            assert result['unreachable'] is True
        if exc_type == HTTPError:
            assert 'error_info' in result

    msg1 = "Either state or command should be provided to further actions."
    msg2 = "When state is present, either controller_id or volume_id must be specified to perform further actions."
    msg3 = "Either state or command should be provided to further actions."

    @pytest.mark.parametrize("input",
                             [{"param": {"xyz": 123}, "msg": msg1}, {"param": {"state": "present"}, "msg": msg2}])
    def test_validate_inputs_error_case_01(self, input):
        f_module = self.get_module_mock(params=input["param"])
        with pytest.raises(Exception) as exc:
            self.module.validate_inputs(f_module)
        assert exc.value.args[0] == input["msg"]

    @pytest.mark.parametrize("input",
                             [{"param": {"state": "present", "controller_id": "abc"}, "msg": msg3}])
    def test_validate_inputs_skip_case(self, input):
        f_module = self.get_module_mock(params=input["param"])
        val = self.module.validate_inputs(f_module)
        assert not val

    def test_get_success_message_case_01(self):
        action = "create"
        message = self.module.get_success_message(action, "JobService/Jobs/JID_1234")
        assert message["msg"] == "Successfully submitted {0} volume task.".format(action)
        assert message["task_uri"] == "JobService/Jobs/JID_1234"
        assert message["task_id"] == "JID_1234"

    def test_get_success_message_case_02(self):
        action = "create"
        message = self.module.get_success_message(action, None)
        assert message["msg"] == "Successfully submitted {0} volume task.".format(action)

    @pytest.mark.parametrize("input", [{"state": "present"}, {"state": "absent"}, {"command": "initialize"}, {"command": None}])
    def test_configure_raid_operation(self, input, redfish_connection_mock_for_storage_volume, mocker):
        f_module = self.get_module_mock(params=input)
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.perform_volume_create_modify',
                     return_value={"msg": "Successfully submitted create volume task.",
                                   "task_uri": "JobService/Jobs",
                                   "task_id": "JID_123"})
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.perform_volume_deletion',
                     return_value={"msg": "Successfully submitted delete volume task.",
                                   "task_uri": "JobService/Jobs",
                                   "task_id": "JID_456"})
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.perform_volume_initialization',
                     return_value={"msg": "Successfully submitted initialize volume task.",
                                   "task_uri": "JobService/Jobs",
                                   "task_id": "JID_789"})
        message = self.module.configure_raid_operation(f_module, redfish_connection_mock_for_storage_volume)
        val = list(input.values())
        if val[0] == "present":
            assert message["msg"] == "Successfully submitted create volume task."
            assert message["task_id"] == "JID_123"
        if val[0] == "absent":
            assert message["msg"] == "Successfully submitted delete volume task."
            assert message["task_id"] == "JID_456"
        if val[0] == "initialize":
            assert message["msg"] == "Successfully submitted initialize volume task."
            assert message["task_id"] == "JID_789"

    def test_perform_volume_initialization_success_case_01(self, mocker, redfish_connection_mock_for_storage_volume,
                                                           storage_volume_base_uri):
        message = {"msg": "Successfully submitted initialize volume task.", "task_uri": "JobService/Jobs",
                   "task_id": "JID_789"}
        f_module = self.get_module_mock(params={"initialize_type": "Fast", "volume_id": "volume_id"})
        obj1 = mocker.patch(MODULE_PATH + 'redfish_storage_volume.check_initialization_progress', return_value=[])
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.perform_storage_volume_action', return_value=message)
        message = self.module.perform_volume_initialization(f_module, redfish_connection_mock_for_storage_volume)
        assert message["msg"] == "Successfully submitted initialize volume task."
        assert message["task_id"] == "JID_789"

    @pytest.mark.parametrize("operations", [[{"OperationName": "initialize", "PercentageComplete": 70}],
                                            [{"OperationName": "initialize"}]])
    def test_perform_volume_initialization_failure_case_01(self, mocker, operations,
                                                           redfish_connection_mock_for_storage_volume):
        f_module = self.get_module_mock(params={"volume_id": "volume_id"})
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.check_initialization_progress', return_value=operations)
        percentage_complete = operations[0].get("PercentageComplete")
        with pytest.raises(Exception) as exc:
            self.module.perform_volume_initialization(f_module, redfish_connection_mock_for_storage_volume)
        if percentage_complete:
            assert exc.value.args[0] == "Cannot perform the configuration operation because the configuration" \
                                        " job 'initialize' in progress is at '70' percentage."
        else:
            assert exc.value.args[0] == "Cannot perform the configuration operations because a" \
                                        " configuration job for the device already exists."

    def test_perform_volume_initialization_failure_case_02(self, mocker, redfish_connection_mock_for_storage_volume):
        f_module = self.get_module_mock(params={})
        with pytest.raises(Exception) as exc:
            self.module.perform_volume_initialization(f_module, redfish_connection_mock_for_storage_volume)
        assert exc.value.args[0] == "'volume_id' option is a required property for initializing a volume."

    def test_perform_volume_deletion_success_case_01(self, mocker, redfish_connection_mock_for_storage_volume,
                                                     redfish_response_mock, storage_volume_base_uri):
        redfish_response_mock.success = True
        f_module = self.get_module_mock(params={"volume_id": "volume_id"})
        f_module.check_mode = False
        message = {"msg": "Successfully submitted delete volume task.", "task_uri": "JobService/Jobs",
                   "task_id": "JID_456"}
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.check_volume_id_exists', return_value=redfish_response_mock)
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.perform_storage_volume_action',
                     return_value=redfish_response_mock)
        self.module.perform_volume_deletion(f_module, redfish_connection_mock_for_storage_volume)
        assert message["msg"] == "Successfully submitted delete volume task."
        assert message["task_id"] == "JID_456"

    def testperform_volume_deletion_failure_case_01(self, mocker, redfish_connection_mock_for_storage_volume):
        f_module = self.get_module_mock(params={})
        with pytest.raises(Exception) as exc:
            self.module.perform_volume_deletion(f_module, redfish_connection_mock_for_storage_volume)
        assert exc.value.args[0] == "'volume_id' option is a required property for deleting a volume."

    def test_perform_volume_deletion_check_mode_case(self, mocker, redfish_connection_mock_for_storage_volume,
                                                     redfish_response_mock, storage_volume_base_uri):
        redfish_response_mock.success = True
        f_module = self.get_module_mock(params={"volume_id": "volume_id"})
        f_module.check_mode = True
        message = {"msg": "Changes found to be applied.", "task_uri": "JobService/Jobs"}
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.check_volume_id_exists', return_value=redfish_response_mock)
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.perform_storage_volume_action',
                     return_value=redfish_response_mock)
        with pytest.raises(Exception) as exc:
            self.module.perform_volume_deletion(f_module, redfish_connection_mock_for_storage_volume)
        assert exc.value.args[0] == "Changes found to be applied."

    def test_perform_volume_deletion_check_mode_failure_case(self, mocker, redfish_connection_mock_for_storage_volume,
                                                             redfish_response_mock, storage_volume_base_uri):
        redfish_response_mock.code = 404
        redfish_response_mock.success = False
        f_module = self.get_module_mock(params={"volume_id": "volume_id"})
        f_module.check_mode = True
        message = {"msg": "No changes found to be applied.", "task_uri": "JobService/Jobs"}
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.check_volume_id_exists', return_value=redfish_response_mock)
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.perform_storage_volume_action',
                     return_value=redfish_response_mock)
        with pytest.raises(Exception) as exc:
            self.module.perform_volume_deletion(f_module, redfish_connection_mock_for_storage_volume)
        assert exc.value.args[0] == "No changes found to be applied."

    def test_perform_volume_create_modify_success_case_01(self, mocker, storage_volume_base_uri,
                                                          redfish_connection_mock_for_storage_volume):
        f_module = self.get_module_mock(params={"volume_id": "volume_id", "controller_id": "controller_id"})
        message = {"msg": "Successfully submitted create volume task.", "task_uri": "JobService/Jobs",
                   "task_id": "JID_123"}
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.check_controller_id_exists', return_value=True)
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.volume_payload', return_value={"payload": "value"})
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.perform_storage_volume_action', return_value=message)
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.check_mode_validation', return_value=None)
        message = self.module.perform_volume_create_modify(f_module, redfish_connection_mock_for_storage_volume)
        assert message["msg"] == "Successfully submitted create volume task."
        assert message["task_id"] == "JID_123"

    def test_perform_volume_create_modify_success_case_02(self, mocker, storage_volume_base_uri,
                                                          redfish_connection_mock_for_storage_volume,
                                                          redfish_response_mock):
        f_module = self.get_module_mock(params={"volume_id": "volume_id"})
        message = {"msg": "Successfully submitted modify volume task.", "task_uri": "JobService/Jobs",
                   "task_id": "JID_123"}
        redfish_response_mock.success = True
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.check_volume_id_exists', return_value=redfish_response_mock)
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.volume_payload', return_value={"payload": "value"})
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.perform_storage_volume_action', return_value=message)
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.check_mode_validation', return_value=None)
        message = self.module.perform_volume_create_modify(f_module, redfish_connection_mock_for_storage_volume)
        assert message["msg"] == "Successfully submitted modify volume task."
        assert message["task_id"] == "JID_123"

    def test_perform_volume_create_modify_success_case_03(self, mocker, storage_volume_base_uri,
                                                          redfish_connection_mock_for_storage_volume,
                                                          redfish_response_mock):
        f_module = self.get_module_mock(params={"volume_id": "volume_id"})
        message = {"msg": "Successfully submitted modify volume task.", "task_uri": "JobService/Jobs",
                   "task_id": "JID_123"}
        redfish_response_mock.success = False
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.check_volume_id_exists', return_value=redfish_response_mock)
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.volume_payload', return_value={"payload": "value"})
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.perform_storage_volume_action', return_value=message)
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.check_mode_validation', return_value=None)
        message = self.module.perform_volume_create_modify(f_module, redfish_connection_mock_for_storage_volume)
        assert message["msg"] == "Successfully submitted modify volume task."
        assert message["task_id"] == "JID_123"

    def test_perform_volume_create_modify_failure_case_01(self, mocker, storage_volume_base_uri,
                                                          redfish_connection_mock_for_storage_volume,
                                                          redfish_response_mock):
        f_module = self.get_module_mock(params={"volume_id": "volume_id"})
        message = {"msg": "Successfully submitted modify volume task.", "task_uri": "JobService/Jobs",
                   "task_id": "JID_123"}
        redfish_response_mock.success = True
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.check_volume_id_exists', return_value=redfish_response_mock)
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.volume_payload', return_value={})
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.perform_storage_volume_action', return_value=message)
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.check_mode_validation', return_value=None)
        with pytest.raises(Exception) as exc:
            self.module.perform_volume_create_modify(f_module, redfish_connection_mock_for_storage_volume)
        assert exc.value.args[0] == "Input options are not provided for the modify volume task."

    def test_perform_storage_volume_action_success_case(self, mocker, redfish_response_mock,
                                                        redfish_connection_mock_for_storage_volume):
        redfish_response_mock.headers.update({"Location": "JobService/Jobs/JID_123"})
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.get_success_message', return_value="message")
        msg = self.module.perform_storage_volume_action("POST", "uri", redfish_connection_mock_for_storage_volume,
                                                        "create", payload={"payload": "value"})
        assert msg == "message"

    def test_perform_storage_volume_action_exception_case(self, redfish_response_mock,
                                                          redfish_connection_mock_for_storage_volume):
        redfish_response_mock.headers.update({"Location": "JobService/Jobs/JID_123"})
        redfish_connection_mock_for_storage_volume.invoke_request.side_effect = HTTPError('https://testhost.com', 400,
                                                                                          '', {}, None)
        with pytest.raises(HTTPError) as ex:
            self.module.perform_storage_volume_action("POST", "uri", redfish_connection_mock_for_storage_volume,
                                                      "create", payload={"payload": "value"})

    def test_check_initialization_progress_case_01(self, mocker, redfish_connection_mock_for_storage_volume,
                                                   redfish_response_mock):
        f_module = self.get_module_mock()
        redfish_response_mock.success = False
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.check_volume_id_exists', return_value=redfish_response_mock)
        opeartion_data = self.module.check_initialization_progress(f_module, redfish_connection_mock_for_storage_volume,
                                                                   "volume_id")
        assert opeartion_data == []

    def test_check_initialization_progress_case_02(self, mocker, redfish_connection_mock_for_storage_volume,
                                                   redfish_response_mock):
        f_module = self.get_module_mock()
        redfish_response_mock.success = True
        redfish_response_mock.json_data = {"Operations": "operation_value"}
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.check_volume_id_exists', return_value=redfish_response_mock)
        opeartion_data = self.module.check_initialization_progress(f_module, redfish_connection_mock_for_storage_volume,
                                                                   "volume_id")
        assert opeartion_data == "operation_value"

    def test_check_volume_id_exists(self, mocker, redfish_connection_mock_for_storage_volume, storage_volume_base_uri,
                                    redfish_response_mock):
        f_module = self.get_module_mock()
        redfish_response_mock.status_code = 200
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.check_specified_identifier_exists_in_the_system',
                     return_value=redfish_response_mock)
        resp = self.module.check_volume_id_exists(f_module, redfish_connection_mock_for_storage_volume, "volume_id")
        assert resp.status_code == 200

    def test_check_controller_id_exists_success_case_01(self, mocker, redfish_connection_mock_for_storage_volume,
                                                        storage_volume_base_uri,
                                                        redfish_response_mock):
        f_module = self.get_module_mock(params={"controller_id": "controller_id"})
        redfish_response_mock.success = True
        redfish_response_mock.json_data = {"Drives": "drive1"}
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.check_specified_identifier_exists_in_the_system',
                     return_value=redfish_response_mock)
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.check_physical_disk_exists',
                     return_value=True)
        output = self.module.check_controller_id_exists(f_module, redfish_connection_mock_for_storage_volume)
        assert output is True

    def test_check_controller_id_exists_failure_case_01(self, mocker, redfish_connection_mock_for_storage_volume,
                                                        storage_volume_base_uri,
                                                        redfish_response_mock):
        f_module = self.get_module_mock(params={"controller_id": "1234"})
        redfish_response_mock.success = False
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.check_specified_identifier_exists_in_the_system',
                     return_value=redfish_response_mock)
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.check_physical_disk_exists',
                     return_value=True)
        with pytest.raises(Exception) as exc:
            self.module.check_controller_id_exists(f_module, redfish_connection_mock_for_storage_volume)
        assert exc.value.args[0] == "Failed to retrieve the details of the specified Controller Id 1234."

    def test_check_specified_identifier_exists_in_the_system_success_case(self,
                                                                          redfish_connection_mock_for_storage_volume,
                                                                          redfish_response_mock):
        f_module = self.get_module_mock(params={"controller_id": "1234"})
        redfish_response_mock.status_code = True
        redfish_response_mock.json_data = {"id": "data"}
        resp = self.module.check_specified_identifier_exists_in_the_system(f_module,
                                                                           redfish_connection_mock_for_storage_volume,
                                                                           "uri",
                                                                           "Specified Controller 123"
                                                                           " does not exist in the System.")
        assert resp.json_data == {"id": "data"}

    def test_check_specified_identifier_exists_in_the_system_exception_case_01(self,
                                                                               redfish_connection_mock_for_storage_volume,
                                                                               redfish_response_mock):
        f_module = self.get_module_mock(params={"controller_id": "1234"})
        redfish_connection_mock_for_storage_volume.invoke_request.side_effect = HTTPError('https://testhost.com',
                                                                                          404,
                                                                                          "Specified Controller 123 does"
                                                                                          " not exist in the System.",
                                                                                          {}, None)
        with pytest.raises(Exception) as exc:
            self.module.check_specified_identifier_exists_in_the_system(f_module,
                                                                        redfish_connection_mock_for_storage_volume,
                                                                        "uri",
                                                                        "Specified Controller 123"
                                                                        " does not exist in the System.")
        assert exc.value.args[0] == "Specified Controller 123 does not exist in the System."

    def test_check_specified_identifier_exists_in_the_system_exception_case_02(self,
                                                                               redfish_connection_mock_for_storage_volume,
                                                                               redfish_response_mock):
        f_module = self.get_module_mock(params={"controller_id": "1234"})
        msg = "http error"
        redfish_connection_mock_for_storage_volume.invoke_request.side_effect = HTTPError('https://testhost.com', 400,
                                                                                          msg, {}, None)
        with pytest.raises(Exception, match=msg) as exc:
            self.module.check_specified_identifier_exists_in_the_system(f_module,
                                                                        redfish_connection_mock_for_storage_volume,
                                                                        "uri",
                                                                        "Specified Controller 123 does not exist in the System.")

    def test_check_specified_identifier_exists_in_the_system_exception_case_03(self,
                                                                               redfish_connection_mock_for_storage_volume,
                                                                               redfish_response_mock):
        f_module = self.get_module_mock(params={"controller_id": "1234"})
        redfish_connection_mock_for_storage_volume.invoke_request.side_effect = URLError('test')
        with pytest.raises(URLError) as exc:
            self.module.check_specified_identifier_exists_in_the_system(f_module,
                                                                        redfish_connection_mock_for_storage_volume,
                                                                        "uri",
                                                                        "Specified Controller"
                                                                        " 123 does not exist in the System.")

    def test_check_physical_disk_exists_success_case_01(self):
        drive = [
            {
                "@odata.id": "/redfish/v1/Systems/System.Embedded.1/"
                             "Storage/Drives/Disk.Bay.0:Enclosure.Internal.0-0:RAID.Mezzanine.1C-1"
            }
        ]
        f_module = self.get_module_mock(params={"controller_id": "RAID.Mezzanine.1C-1",
                                                "drives": ["Disk.Bay.0:Enclosure.Internal.0-0:RAID.Mezzanine.1C-1"]})
        val = self.module.check_physical_disk_exists(f_module, drive)
        assert val

    def test_check_physical_disk_exists_success_case_02(self):
        drive = [
            {
                "@odata.id": "/redfish/v1/Systems/System.Embedded.1/Storage/"
                             "Drives/Disk.Bay.0:Enclosure.Internal.0-0:RAID.Mezzanine.1C-1"
            }
        ]
        f_module = self.get_module_mock(params={"controller_id": "RAID.Mezzanine.1C-1", "drives": []})
        val = self.module.check_physical_disk_exists(f_module, drive)
        assert val

    def test_check_physical_disk_exists_error_case_01(self):
        drive = [
            {
                "@odata.id": "/redfish/v1/Systems/System.Embedded.1/"
                             "Storage/Drives/Disk.Bay.0:Enclosure.Internal.0-0:RAID.Mezzanine.1C-1"
            }
        ]
        f_module = self.get_module_mock(params={"controller_id": "RAID.Mezzanine.1C-1", "drives": ["invalid_drive"]})
        with pytest.raises(Exception) as exc:
            self.module.check_physical_disk_exists(f_module, drive)
        assert exc.value.args[0] == "Following Drive(s) invalid_drive are not attached to the specified" \
                                    " Controller Id: RAID.Mezzanine.1C-1."

    def test_check_physical_disk_exists_error_case_02(self):
        drive = [
        ]
        f_module = self.get_module_mock(params={"controller_id": "RAID.Mezzanine.1C-1",
                                                "drives": ["Disk.Bay.0:Enclosure.Internal.0-0:RAID.Mezzanine.1C-1"]})
        with pytest.raises(Exception) as exc:
            self.module.check_physical_disk_exists(f_module, drive)
        assert exc.value.args[0] == "No Drive(s) are attached to the specified Controller Id: RAID.Mezzanine.1C-1."

    def test_volume_payload_case_01(self, storage_volume_base_uri):
        param = {
            "drives": ["Disk.Bay.0:Enclosure.Internal.0-0:RAID.Mezzanine.1C-1"],
            "capacity_bytes": 299439751168,
            "block_size_bytes": 512,
            "encryption_types": "NativeDriveEncryption",
            "encrypted": True,
            "raid_type": "RAID0",
            "name": "VD1",
            "optimum_io_size_bytes": 65536,
            "apply_time": "Immediate",
            "oem": {"Dell": {"DellVirtualDisk": {"BusProtocol": "SAS", "Cachecade": "NonCachecadeVD",
                                                 "DiskCachePolicy": "Disabled",
                                                 "LockStatus": "Unlocked",
                                                 "MediaType": "HardDiskDrive",
                                                 "ReadCachePolicy": "NoReadAhead",
                                                 "SpanDepth": 1,
                                                 "SpanLength": 2,
                                                 "WriteCachePolicy": "WriteThrough"}}}}
        f_module = self.get_module_mock(params=param)
        payload = self.module.volume_payload(f_module)
        assert payload["Drives"][0]["@odata.id"] == "/redfish/v1/Systems/System.Embedded.1/Storage/" \
                                                    "Drives/Disk.Bay.0:Enclosure.Internal.0-0:RAID.Mezzanine.1C-1"
        assert payload["RAIDType"] == "RAID0"
        assert payload["Name"] == "VD1"
        assert payload["BlockSizeBytes"] == 512
        assert payload["CapacityBytes"] == 299439751168
        assert payload["OptimumIOSizeBytes"] == 65536
        assert payload["Encrypted"] is True
        assert payload["EncryptionTypes"] == ["NativeDriveEncryption"]
        assert payload["Dell"]["DellVirtualDisk"]["ReadCachePolicy"] == "NoReadAhead"
        assert payload["@Redfish.OperationApplyTime"] == "Immediate"

    def test_volume_payload_case_02(self):
        param = {"block_size_bytes": 512,
                 "raid_type": "RAID0",
                 "name": "VD1",
                 "optimum_io_size_bytes": 65536}
        f_module = self.get_module_mock(params=param)
        payload = self.module.volume_payload(f_module)
        assert payload["RAIDType"] == "RAID0"
        assert payload["Name"] == "VD1"
        assert payload["BlockSizeBytes"] == 512
        assert payload["OptimumIOSizeBytes"] == 65536

    def test_volume_payload_case_03(self, storage_volume_base_uri):
        """Testing encrypted value in case value is passed false"""
        param = {
            "drives": ["Disk.Bay.0:Enclosure.Internal.0-0:RAID.Mezzanine.1C-1"],
            "capacity_bytes": 299439751168,
            "block_size_bytes": 512,
            "encryption_types": "NativeDriveEncryption",
            "encrypted": False,
            "raid_type": "RAID0",
            "name": "VD1",
            "optimum_io_size_bytes": 65536,
            "oem": {"Dell": {"DellVirtualDisk": {"BusProtocol": "SAS", "Cachecade": "NonCachecadeVD",
                                                 "DiskCachePolicy": "Disabled",
                                                 "LockStatus": "Unlocked",
                                                 "MediaType": "HardDiskDrive",
                                                 "ReadCachePolicy": "NoReadAhead",
                                                 "SpanDepth": 1,
                                                 "SpanLength": 2,
                                                 "WriteCachePolicy": "WriteThrough"}}}}
        f_module = self.get_module_mock(params=param)
        payload = self.module.volume_payload(f_module)
        assert payload["Drives"][0]["@odata.id"] == "/redfish/v1/Systems/System.Embedded.1/" \
                                                    "Storage/Drives/Disk.Bay.0:Enclosure.Internal.0-0:RAID.Mezzanine.1C-1"
        assert payload["RAIDType"] == "RAID0"
        assert payload["Name"] == "VD1"
        assert payload["BlockSizeBytes"] == 512
        assert payload["CapacityBytes"] == 299439751168
        assert payload["OptimumIOSizeBytes"] == 65536
        assert payload["Encrypted"] is False
        assert payload["EncryptionTypes"] == ["NativeDriveEncryption"]
        assert payload["Dell"]["DellVirtualDisk"]["ReadCachePolicy"] == "NoReadAhead"

    def test_volume_payload_case_04(self, storage_volume_base_uri):
        param = {
            "drives": ["Disk.Bay.0:Enclosure.Internal.0-0:RAID.Mezzanine.1C-1"],
            "capacity_bytes": 299439751168,
            "block_size_bytes": 512,
            "encryption_types": "NativeDriveEncryption",
            "encrypted": True,
            "volume_type": "NonRedundant",
            "name": "VD1",
            "optimum_io_size_bytes": 65536,
            "oem": {"Dell": {"DellVirtualDisk": {"BusProtocol": "SAS", "Cachecade": "NonCachecadeVD",
                                                 "DiskCachePolicy": "Disabled",
                                                 "LockStatus": "Unlocked",
                                                 "MediaType": "HardDiskDrive",
                                                 "ReadCachePolicy": "NoReadAhead",
                                                 "SpanDepth": 1,
                                                 "SpanLength": 2,
                                                 "WriteCachePolicy": "WriteThrough"}}}}
        f_module = self.get_module_mock(params=param)
        payload = self.module.volume_payload(f_module)
        assert payload["Drives"][0]["@odata.id"] == "/redfish/v1/Systems/System.Embedded.1/Storage/" \
                                                    "Drives/Disk.Bay.0:Enclosure.Internal.0-0:RAID.Mezzanine.1C-1"
        assert payload["RAIDType"] == "RAID0"
        assert payload["Name"] == "VD1"
        assert payload["BlockSizeBytes"] == 512
        assert payload["CapacityBytes"] == 299439751168
        assert payload["OptimumIOSizeBytes"] == 65536
        assert payload["Encrypted"] is True
        assert payload["EncryptionTypes"] == ["NativeDriveEncryption"]
        assert payload["Dell"]["DellVirtualDisk"]["ReadCachePolicy"] == "NoReadAhead"

    def test_volume_payload_case_05(self, storage_volume_base_uri):
        param = {
            "drives": ["Disk.Bay.0:Enclosure.Internal.0-0:RAID.Mezzanine.1C-1",
                       "Disk.Bay.0:Enclosure.Internal.0-1:RAID.Mezzanine.1C-1",
                       "Disk.Bay.0:Enclosure.Internal.0-2:RAID.Mezzanine.1C-1",
                       "Disk.Bay.0:Enclosure.Internal.0-3:RAID.Mezzanine.1C-1"],
            "capacity_bytes": 299439751168,
            "block_size_bytes": 512,
            "encryption_types": "NativeDriveEncryption",
            "encrypted": True,
            "raid_type": "RAID6",
            "name": "VD1",
            "optimum_io_size_bytes": 65536,
            "oem": {"Dell": {"DellVirtualDisk": {"BusProtocol": "SAS", "Cachecade": "NonCachecadeVD",
                                                 "DiskCachePolicy": "Disabled",
                                                 "LockStatus": "Unlocked",
                                                 "MediaType": "HardDiskDrive",
                                                 "ReadCachePolicy": "NoReadAhead",
                                                 "SpanDepth": 1,
                                                 "SpanLength": 2,
                                                 "WriteCachePolicy": "WriteThrough"}}}}
        f_module = self.get_module_mock(params=param)
        payload = self.module.volume_payload(f_module)
        assert payload["Drives"][0]["@odata.id"] == "/redfish/v1/Systems/System.Embedded.1/Storage/" \
                                                    "Drives/Disk.Bay.0:Enclosure.Internal.0-0:RAID.Mezzanine.1C-1"
        assert payload["RAIDType"] == "RAID6"
        assert payload["Name"] == "VD1"
        assert payload["BlockSizeBytes"] == 512
        assert payload["CapacityBytes"] == 299439751168
        assert payload["OptimumIOSizeBytes"] == 65536
        assert payload["Encrypted"] is True
        assert payload["EncryptionTypes"] == ["NativeDriveEncryption"]
        assert payload["Dell"]["DellVirtualDisk"]["ReadCachePolicy"] == "NoReadAhead"

    def test_volume_payload_case_06(self, storage_volume_base_uri):
        param = {
            "drives": ["Disk.Bay.0:Enclosure.Internal.0-0:RAID.Mezzanine.1C-1",
                       "Disk.Bay.0:Enclosure.Internal.0-1:RAID.Mezzanine.1C-1",
                       "Disk.Bay.0:Enclosure.Internal.0-2:RAID.Mezzanine.1C-1",
                       "Disk.Bay.0:Enclosure.Internal.0-3:RAID.Mezzanine.1C-1",
                       "Disk.Bay.0:Enclosure.Internal.0-4:RAID.Mezzanine.1C-1",
                       "Disk.Bay.0:Enclosure.Internal.0-5:RAID.Mezzanine.1C-1",
                       "Disk.Bay.0:Enclosure.Internal.0-6:RAID.Mezzanine.1C-1",
                       "Disk.Bay.0:Enclosure.Internal.0-7:RAID.Mezzanine.1C-1"],
            "capacity_bytes": 299439751168,
            "block_size_bytes": 512,
            "encryption_types": "NativeDriveEncryption",
            "encrypted": True,
            "raid_type": "RAID60",
            "name": "VD1",
            "optimum_io_size_bytes": 65536,
            "oem": {"Dell": {"DellVirtualDisk": {"BusProtocol": "SAS", "Cachecade": "NonCachecadeVD",
                                                 "DiskCachePolicy": "Disabled",
                                                 "LockStatus": "Unlocked",
                                                 "MediaType": "HardDiskDrive",
                                                 "ReadCachePolicy": "NoReadAhead",
                                                 "SpanDepth": 1,
                                                 "SpanLength": 2,
                                                 "WriteCachePolicy": "WriteThrough"}}}}
        f_module = self.get_module_mock(params=param)
        payload = self.module.volume_payload(f_module)
        assert payload["Drives"][0]["@odata.id"] == "/redfish/v1/Systems/System.Embedded.1/Storage/" \
                                                    "Drives/Disk.Bay.0:Enclosure.Internal.0-0:RAID.Mezzanine.1C-1"
        assert payload["RAIDType"] == "RAID60"
        assert payload["Name"] == "VD1"
        assert payload["BlockSizeBytes"] == 512
        assert payload["CapacityBytes"] == 299439751168
        assert payload["OptimumIOSizeBytes"] == 65536
        assert payload["Encrypted"] is True
        assert payload["EncryptionTypes"] == ["NativeDriveEncryption"]
        assert payload["Dell"]["DellVirtualDisk"]["ReadCachePolicy"] == "NoReadAhead"

    def test_fetch_storage_resource_success_case_01(self, redfish_connection_mock_for_storage_volume,
                                                    redfish_response_mock):
        f_module = self.get_module_mock()
        redfish_response_mock.json_data = {
            "@odata.id": "/redfish/v1/Systems",
            "Members": [
                {
                    "@odata.id": "/redfish/v1/Systems/System.Embedded.1"
                }
            ],
            "Storage": {
                "@odata.id": "/redfish/v1/Systems/System.Embedded.1/Storage"
            },
        }
        redfish_connection_mock_for_storage_volume.root_uri = "/redfish/v1/"
        self.module.fetch_storage_resource(f_module, redfish_connection_mock_for_storage_volume)
        assert self.module.storage_collection_map["storage_base_uri"] == "/redfish/v1/Systems/System.Embedded.1/Storage"

    def test_fetch_storage_resource_error_case_01(self, redfish_connection_mock_for_storage_volume,
                                                  redfish_response_mock):
        f_module = self.get_module_mock()
        redfish_response_mock.json_data = {
            "@odata.id": "/redfish/v1/Systems",
            "Members": [
                {
                    "@odata.id": "/redfish/v1/Systems/System.Embedded.1"
                }
            ],
        }
        redfish_connection_mock_for_storage_volume.root_uri = "/redfish/v1/"
        with pytest.raises(Exception) as exc:
            self.module.fetch_storage_resource(f_module, redfish_connection_mock_for_storage_volume)
        assert exc.value.args[0] == "Target out-of-band controller does not support storage feature using Redfish API."

    def test_fetch_storage_resource_error_case_02(self, redfish_connection_mock_for_storage_volume,
                                                  redfish_response_mock):
        f_module = self.get_module_mock()
        redfish_response_mock.json_data = {
            "@odata.id": "/redfish/v1/Systems",
            "Members": [
            ],
        }
        redfish_connection_mock_for_storage_volume.root_uri = "/redfish/v1/"
        with pytest.raises(Exception) as exc:
            self.module.fetch_storage_resource(f_module, redfish_connection_mock_for_storage_volume)
        assert exc.value.args[0] == "Target out-of-band controller does not support storage feature using Redfish API."

    def test_fetch_storage_resource_error_case_03(self, redfish_connection_mock_for_storage_volume,
                                                  redfish_response_mock):
        f_module = self.get_module_mock()
        msg = "Target out-of-band controller does not support storage feature using Redfish API."
        redfish_connection_mock_for_storage_volume.root_uri = "/redfish/v1/"
        redfish_connection_mock_for_storage_volume.invoke_request.side_effect = HTTPError('https://testhost.com', 404,
                                                                                          json.dumps(msg), {}, None)
        with pytest.raises(Exception) as exc:
            self.module.fetch_storage_resource(f_module, redfish_connection_mock_for_storage_volume)

    def test_fetch_storage_resource_error_case_04(self, redfish_connection_mock_for_storage_volume,
                                                  redfish_response_mock):
        f_module = self.get_module_mock()
        msg = "http error"
        redfish_connection_mock_for_storage_volume.root_uri = "/redfish/v1/"
        redfish_connection_mock_for_storage_volume.invoke_request.side_effect = HTTPError('https://testhost.com', 400,
                                                                                          msg, {}, None)
        with pytest.raises(Exception, match=msg) as exc:
            self.module.fetch_storage_resource(f_module, redfish_connection_mock_for_storage_volume)

    def test_fetch_storage_resource_error_case_05(self, redfish_connection_mock_for_storage_volume,
                                                  redfish_response_mock):
        f_module = self.get_module_mock()
        msg = "connection error"
        redfish_connection_mock_for_storage_volume.root_uri = "/redfish/v1/"
        redfish_connection_mock_for_storage_volume.invoke_request.side_effect = URLError(msg)
        with pytest.raises(Exception, match=msg) as exc:
            self.module.fetch_storage_resource(f_module, redfish_connection_mock_for_storage_volume)

    def test_check_mode_validation(self, redfish_connection_mock_for_storage_volume,
                                   redfish_response_mock, storage_volume_base_uri):
        param = {"drives": ["Disk.Bay.0:Enclosure.Internal.0-0:RAID.Integrated.1-1"],
                 "capacity_bytes": 214748364800, "block_size_bytes": 512, "encryption_types": "NativeDriveEncryption",
                 "encrypted": False, "raid_type": "RAID0", "optimum_io_size_bytes": 65536}
        f_module = self.get_module_mock(params=param)
        f_module.check_mode = True
        with pytest.raises(Exception) as exc:
            self.module.check_mode_validation(
                f_module, redfish_connection_mock_for_storage_volume, "create",
                "/redfish/v1/Systems/System.Embedded.1/Storage/RAID.Integrated.1-1/Volumes/")
        assert exc.value.args[0] == "Changes found to be applied."
        redfish_response_mock.json_data = {"Members@odata.count": 0}
        with pytest.raises(Exception) as exc:
            self.module.check_mode_validation(
                f_module, redfish_connection_mock_for_storage_volume, "create",
                "/redfish/v1/Systems/System.Embedded.1/Storage/RAID.Integrated.1-1/Volumes/")
        assert exc.value.args[0] == "Changes found to be applied."
        redfish_response_mock.json_data = {
            "Members@odata.count": 1, "Id": "Disk.Virtual.0:RAID.Integrated.1-1",
            "Members": [{"@odata.id": "/redfish/v1/Systems/System.Embedded.1/Storage/"
                                      "RAID.Integrated.1-1/Volumes/Disk.Virtual.0:RAID.Integrated.1-1"}],
            "Name": "VD0", "BlockSizeBytes": 512, "CapacityBytes": 214748364800, "Encrypted": False,
            "EncryptionTypes": ["NativeDriveEncryption"], "OptimumIOSizeBytes": 65536, "RAIDType": "RAID0",
            "Links": {"Drives": [{"@odata.id": "Drives/Disk.Bay.0:Enclosure.Internal.0-0:RAID.Integrated.1-1"}]}}
        param.update({"name": "VD0"})
        f_module = self.get_module_mock(params=param)
        f_module.check_mode = True
        with pytest.raises(Exception) as exc:
            self.module.check_mode_validation(
                f_module, redfish_connection_mock_for_storage_volume, "create",
                "/redfish/v1/Systems/System.Embedded.1/Storage/RAID.Integrated.1-1/Volumes/")
        assert exc.value.args[0] == "No changes found to be applied."

    def test_check_mode_validation_01(self, redfish_connection_mock_for_storage_volume,
                                      redfish_response_mock, storage_volume_base_uri):
        param1 = {"volume_id": None, 'name': None}
        f_module = self.get_module_mock(params=param1)
        f_module.check_mode = False
        result = self.module.check_mode_validation(f_module,
                                                   redfish_connection_mock_for_storage_volume,
                                                   "",
                                                   "/redfish/v1/Systems/System.Embedded.1/Storage/RAID.Integrated.1-1/Volumes/")
        assert not result

    def test_check_raid_type_supported_success_case01(self, mocker, redfish_response_mock, storage_volume_base_uri,
                                                      redfish_connection_mock_for_storage_volume):
        param = {"raid_type": "RAID0", "controller_id": "controller_id"}
        f_module = self.get_module_mock(params=param)
        redfish_response_mock.success = True
        redfish_response_mock.json_data = {'StorageControllers': [{'SupportedRAIDTypes': ['RAID0', 'RAID6', 'RAID60']}]}
        self.module.check_raid_type_supported(f_module,
                                              redfish_connection_mock_for_storage_volume)

    def test_check_raid_type_supported_success_case02(self, mocker, redfish_response_mock, storage_volume_base_uri,
                                                      redfish_connection_mock_for_storage_volume):
        param = {"volume_type": "NonRedundant", "controller_id": "controller_id"}
        f_module = self.get_module_mock(params=param)
        redfish_response_mock.success = True
        redfish_response_mock.json_data = {'StorageControllers': [{'SupportedRAIDTypes': ['RAID0', 'RAID6', 'RAID60']}]}
        self.module.check_raid_type_supported(f_module,
                                              redfish_connection_mock_for_storage_volume)

    def test_check_raid_type_supported_success_case03(self, mocker, redfish_response_mock, storage_volume_base_uri,
                                                      redfish_connection_mock_for_storage_volume):
        param = {"raid_type": "RAID6", "controller_id": "controller_id"}
        f_module = self.get_module_mock(params=param)
        redfish_response_mock.success = True
        redfish_response_mock.json_data = {'StorageControllers': [{'SupportedRAIDTypes': ['RAID0', 'RAID6', 'RAID60']}]}
        self.module.check_raid_type_supported(f_module,
                                              redfish_connection_mock_for_storage_volume)

    def test_check_raid_type_supported_success_case04(self, mocker, redfish_response_mock, storage_volume_base_uri,
                                                      redfish_connection_mock_for_storage_volume):
        param = {"raid_type": "RAID60", "controller_id": "controller_id"}
        f_module = self.get_module_mock(params=param)
        redfish_response_mock.success = True
        redfish_response_mock.json_data = {'StorageControllers': [{'SupportedRAIDTypes': ['RAID0', 'RAID6', 'RAID60']}]}
        self.module.check_raid_type_supported(f_module,
                                              redfish_connection_mock_for_storage_volume)

    def test_check_raid_type_supported_failure_case(self, mocker, redfish_response_mock, storage_volume_base_uri,
                                                    redfish_connection_mock_for_storage_volume):
        param = {"raid_type": "RAID9", "controller_id": "controller_id"}
        f_module = self.get_module_mock(params=param)
        redfish_response_mock.success = True
        redfish_response_mock.json_data = {'StorageControllers': [{'SupportedRAIDTypes': ['RAID0', 'RAID6', 'RAID60']}]}
        with pytest.raises(Exception) as exc:
            self.module.check_raid_type_supported(f_module,
                                                  redfish_connection_mock_for_storage_volume)
        assert exc.value.args[0] == "RAID Type RAID9 is not supported."

    def test_check_raid_type_supported_exception_case(self, redfish_response_mock,
                                                      redfish_connection_mock_for_storage_volume,
                                                      storage_volume_base_uri):
        param = {"volume_type": "NonRedundant", "controller_id": "controller_id"}
        f_module = self.get_module_mock(params=param)
        redfish_connection_mock_for_storage_volume.invoke_request.side_effect = HTTPError('https://testhost.com', 400,
                                                                                          '', {}, None)
        with pytest.raises(HTTPError) as ex:
            self.module.check_raid_type_supported(f_module, redfish_connection_mock_for_storage_volume)

    def test_get_apply_time_success_case_01(self, redfish_response_mock,
                                            redfish_connection_mock_for_storage_volume,
                                            storage_volume_base_uri):
        param = {"controller_id": "controller_id", "apply_time": "Immediate"}
        f_module = self.get_module_mock(params=param)
        redfish_response_mock.success = True
        redfish_response_mock.json_data = {"@Redfish.OperationApplyTimeSupport": {"SupportedValues": ["Immediate"]}}
        self.module.get_apply_time(f_module,
                                   redfish_connection_mock_for_storage_volume,
                                   controller_id="controller_id")

    def test_get_apply_time_success_case_02(self, redfish_response_mock,
                                            redfish_connection_mock_for_storage_volume,
                                            storage_volume_base_uri):
        param = {"controller_id": "controller_id"}
        f_module = self.get_module_mock(params=param)
        redfish_response_mock.success = True
        redfish_response_mock.json_data = {"@Redfish.OperationApplyTimeSupport": {"SupportedValues": ["Immediate"]}}
        self.module.get_apply_time(f_module,
                                   redfish_connection_mock_for_storage_volume,
                                   controller_id="controller_id")

    def test_get_apply_time_supported_failure_case(self, redfish_response_mock,
                                                   redfish_connection_mock_for_storage_volume,
                                                   storage_volume_base_uri):
        param = {"controller_id": "controller_id", "apply_time": "Immediate"}
        f_module = self.get_module_mock(params=param)
        redfish_response_mock.success = True
        redfish_response_mock.json_data = {"@Redfish.OperationApplyTimeSupport": {"SupportedValues": ["OnReset"]}}
        with pytest.raises(Exception) as exc:
            self.module.get_apply_time(f_module,
                                       redfish_connection_mock_for_storage_volume,
                                       controller_id="controller_id")
        assert exc.value.args[0] == "Apply time Immediate \
is not supported. The supported values are ['OnReset']. Enter the valid values and retry the operation."

    def test_get_apply_time_supported_exception_case(self, redfish_response_mock,
                                                     redfish_connection_mock_for_storage_volume,
                                                     storage_volume_base_uri):
        param = {"controller_id": "controller_id", "apply_time": "Immediate"}
        f_module = self.get_module_mock(params=param)
        redfish_connection_mock_for_storage_volume.invoke_request.side_effect = HTTPError('https://testhost.com', 400,
                                                                                          '', {}, None)
        with pytest.raises(HTTPError) as ex:
            self.module.get_apply_time(f_module, redfish_connection_mock_for_storage_volume,
                                       controller_id="controller_id")

    def test_check_apply_time_supported_and_reboot_required_success_case01(self, mocker,
                                                                           redfish_response_mock,
                                                                           redfish_connection_mock_for_storage_volume,
                                                                           storage_volume_base_uri):
        param = {"reboot_server": True}
        f_module = self.get_module_mock(params=param)
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.get_apply_time',
                     return_value="OnReset")
        apply_time = self.module.get_apply_time(f_module, redfish_connection_mock_for_storage_volume)
        val = self.module.check_apply_time_supported_and_reboot_required(f_module,
                                                                         redfish_connection_mock_for_storage_volume,
                                                                         controller_id="controller_id")
        assert val

    def test_check_apply_time_supported_and_reboot_required_success_case02(self, mocker,
                                                                           redfish_response_mock,
                                                                           redfish_connection_mock_for_storage_volume,
                                                                           storage_volume_base_uri):
        param = {"reboot_server": False}
        f_module = self.get_module_mock(params=param)
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.get_apply_time',
                     return_value="Immediate")
        apply_time = self.module.get_apply_time(f_module, redfish_connection_mock_for_storage_volume)
        val = self.module.check_apply_time_supported_and_reboot_required(f_module,
                                                                         redfish_connection_mock_for_storage_volume,
                                                                         controller_id="controller_id")
        assert not val

    def test_check_job_tracking_required_success_case01(self, mocker, redfish_response_mock,
                                                        redfish_connection_mock_for_storage_volume,
                                                        storage_volume_base_uri):
        param = {"job_wait": True}
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.get_apply_time',
                     return_value="OnReset")
        f_module = self.get_module_mock(params=param)
        redfish_response_mock.success = True
        val = self.module.check_job_tracking_required(f_module,
                                                      redfish_connection_mock_for_storage_volume,
                                                      reboot_required=False,
                                                      controller_id="controller_id")
        assert not val

    def test_check_job_tracking_required_success_case02(self, mocker, redfish_response_mock,
                                                        redfish_connection_mock_for_storage_volume,
                                                        storage_volume_base_uri):
        param = {"job_wait": True}
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.get_apply_time',
                     return_value="Immediate")
        f_module = self.get_module_mock(params=param)
        val = self.module.check_job_tracking_required(f_module,
                                                      redfish_connection_mock_for_storage_volume,
                                                      reboot_required=True,
                                                      controller_id="controller_id")
        assert val

    def test_check_job_tracking_required_success_case03(self, mocker, redfish_response_mock,
                                                        redfish_connection_mock_for_storage_volume,
                                                        storage_volume_base_uri):
        param = {"job_wait": False}
        mocker.patch(MODULE_PATH + 'redfish_storage_volume.get_apply_time',
                     return_value="Immediate")
        f_module = self.get_module_mock(params=param)
        val = self.module.check_job_tracking_required(f_module,
                                                      redfish_connection_mock_for_storage_volume,
                                                      reboot_required=True,
                                                      controller_id=None)
        assert not val

    def test_perform_reboot_timeout_case(self, mocker, redfish_response_mock,
                                         redfish_connection_mock_for_storage_volume,
                                         storage_volume_base_uri,
                                         redfish_default_args):
        param = {"force_reboot": False}
        f_module = self.get_module_mock(params=param)
        mocker.patch(MODULE_PATH + "redfish_storage_volume.wait_for_redfish_reboot_job",
                     return_value=({"JobState": "Completed", "Id": "JID_123456789"}, True, ""))
        mocker.patch(MODULE_PATH + "redfish_storage_volume.wait_for_job_completion",
                     return_value=("", "The job is not complete after 2 seconds."))
        with pytest.raises(Exception) as exc:
            self.module.perform_reboot(f_module, redfish_connection_mock_for_storage_volume)
        assert exc.value.args[0] == "The job is not complete after 2 seconds."

    def test_perform_reboot_success_case01(self, mocker, redfish_response_mock,
                                           redfish_connection_mock_for_storage_volume,
                                           storage_volume_base_uri,
                                           redfish_default_args):
        param = {"force_reboot": False}
        f_module = self.get_module_mock(params=param)
        mocker.patch(MODULE_PATH + "redfish_storage_volume.wait_for_redfish_reboot_job",
                     return_value=({"JobState": "Completed", "Id": "JID_123456789"}, True, ""))
        redfish_response_mock.json_data = {"JobState": "Completed"}
        mocker.patch(MODULE_PATH + "redfish_storage_volume.wait_for_job_completion",
                     return_value=(redfish_response_mock, "The job is completed."))
        val = self.module.perform_reboot(f_module, redfish_connection_mock_for_storage_volume)
        assert not val

    def test_perform_reboot_success_case02(self, mocker, redfish_response_mock,
                                           redfish_connection_mock_for_storage_volume,
                                           storage_volume_base_uri,
                                           redfish_default_args):
        param = {"force_reboot": True}
        f_module = self.get_module_mock(params=param)
        mocker.patch(MODULE_PATH + "redfish_storage_volume.wait_for_redfish_reboot_job",
                     return_value=({"JobState": "Failed", "Id": "JID_123456789"}, True, ""))
        redfish_response_mock.json_data = {"JobState": "Failed"}
        mocker.patch(MODULE_PATH + "redfish_storage_volume.wait_for_job_completion",
                     return_value=(redfish_response_mock, "The job is failed."))
        mocker.patch(MODULE_PATH + "redfish_storage_volume.perform_force_reboot",
                     return_value=True)
        val = self.module.perform_reboot(f_module, redfish_connection_mock_for_storage_volume)
        assert not val

    def test_perform_reboot_without_output_case(self, mocker, redfish_response_mock,
                                                redfish_connection_mock_for_storage_volume,
                                                storage_volume_base_uri,
                                                redfish_default_args):
        param = {"force_reboot": False}
        f_module = self.get_module_mock(params=param)
        mocker.patch(MODULE_PATH + "redfish_storage_volume.wait_for_redfish_reboot_job",
                     return_value=("", False, ""))

        val = self.module.perform_reboot(f_module, redfish_connection_mock_for_storage_volume)
        assert not val

    def test_perform_force_reboot_timeout_case(self, mocker, redfish_response_mock,
                                               redfish_connection_mock_for_storage_volume,
                                               storage_volume_base_uri,
                                               redfish_default_args):
        param = {"force_reboot": False}
        f_module = self.get_module_mock(params=param)
        mocker.patch(MODULE_PATH + "redfish_storage_volume.wait_for_redfish_reboot_job",
                     return_value=({"JobState": "Completed", "Id": "JID_123456789"}, True, ""))
        mocker.patch(MODULE_PATH + "redfish_storage_volume.wait_for_job_completion",
                     return_value=("", "The job is not complete after 2 seconds."))
        with pytest.raises(Exception) as exc:
            self.module.perform_force_reboot(f_module, redfish_connection_mock_for_storage_volume)
        assert exc.value.args[0] == "The job is not complete after 2 seconds."

    def test_perform_force_reboot_success_case01(self, mocker, redfish_response_mock,
                                                 redfish_connection_mock_for_storage_volume,
                                                 storage_volume_base_uri,
                                                 redfish_default_args):
        param = {"force_reboot": False}
        f_module = self.get_module_mock(params=param)
        mocker.patch(MODULE_PATH + "redfish_storage_volume.wait_for_redfish_reboot_job",
                     return_value=({"JobState": "Completed", "Id": "JID_123456789"}, True, ""))
        redfish_response_mock.json_data = {"JobState": "Completed"}
        mocker.patch(MODULE_PATH + "redfish_storage_volume.wait_for_job_completion",
                     return_value=(redfish_response_mock, "The job is completed."))
        val = self.module.perform_force_reboot(f_module, redfish_connection_mock_for_storage_volume)
        assert not val

    def test_perform_reboot_success_case02(self, mocker, redfish_response_mock,
                                           redfish_connection_mock_for_storage_volume,
                                           storage_volume_base_uri,
                                           redfish_default_args):
        param = {"force_reboot": True}
        f_module = self.get_module_mock(params=param)
        mocker.patch(MODULE_PATH + "redfish_storage_volume.wait_for_redfish_reboot_job",
                     return_value=({"JobState": "Completed", "Id": "JID_123456789"}, True, ""))
        redfish_response_mock.json_data = {"JobState": "Failed"}
        mocker.patch(MODULE_PATH + "redfish_storage_volume.wait_for_job_completion",
                     return_value=(redfish_response_mock, "The job is completed."))
        with pytest.raises(Exception) as exc:
            self.module.perform_force_reboot(f_module, redfish_connection_mock_for_storage_volume)
        assert exc.value.args[0] == "Failed to reboot the server."

    def test_perform_force_reboot_without_output_case(self, mocker, redfish_response_mock,
                                                      redfish_connection_mock_for_storage_volume,
                                                      storage_volume_base_uri,
                                                      redfish_default_args):
        f_module = self.get_module_mock()
        mocker.patch(MODULE_PATH + "redfish_storage_volume.wait_for_redfish_reboot_job",
                     return_value=("", False, ""))
        val = self.module.perform_force_reboot(f_module, redfish_connection_mock_for_storage_volume)
        assert not val

    def test_track_job_success_case01(self, mocker, redfish_response_mock,
                                      redfish_connection_mock_for_storage_volume,
                                      storage_volume_base_uri,
                                      redfish_default_args):
        job_id = "JID_123456789"
        job_url = "/redfish/v1/Managers/iDRAC.Embedded.1/JID_123456789"
        f_module = self.get_module_mock()
        redfish_response_mock.json_data = {"JobState": "Scheduled"}
        mocker.patch(MODULE_PATH + "redfish_storage_volume.wait_for_job_completion",
                     return_value=(redfish_response_mock, "The job is scheduled."))
        with pytest.raises(Exception) as exc:
            self.module.track_job(f_module, redfish_connection_mock_for_storage_volume, job_id, job_url)
        assert exc.value.args[0] == "The job is successfully submitted."

    def test_track_job_success_case02(self, mocker,
                                      redfish_connection_mock_for_storage_volume,
                                      storage_volume_base_uri,
                                      redfish_default_args):
        job_id = "JID_123456789"
        job_url = "/redfish/v1/Managers/iDRAC.Embedded.1/JID_123456789"
        f_module = self.get_module_mock()
        redfish_response_mock = {}
        mocker.patch(MODULE_PATH + "redfish_storage_volume.wait_for_job_completion",
                     return_value=(redfish_response_mock, "The job has no response."))
        with pytest.raises(Exception) as exc:
            self.module.track_job(f_module, redfish_connection_mock_for_storage_volume, job_id, job_url)
        assert exc.value.args[0] == "The job has no response."

    def test_track_job_success_case03(self, mocker, redfish_response_mock,
                                      redfish_connection_mock_for_storage_volume,
                                      storage_volume_base_uri,
                                      redfish_default_args):
        job_id = "JID_123456789"
        job_url = "/redfish/v1/Managers/iDRAC.Embedded.1/JID_123456789"
        f_module = self.get_module_mock()
        redfish_response_mock.json_data = {"JobState": "Failed"}
        mocker.patch(MODULE_PATH + "redfish_storage_volume.wait_for_job_completion",
                     return_value=(redfish_response_mock, "The job is failed."))
        with pytest.raises(Exception) as exc:
            self.module.track_job(f_module, redfish_connection_mock_for_storage_volume, job_id, job_url)
        assert exc.value.args[0] == "Unable to complete the task initiated for creating the storage volume."

    def test_track_job_success_case04(self, mocker, redfish_response_mock,
                                      redfish_connection_mock_for_storage_volume,
                                      storage_volume_base_uri,
                                      redfish_default_args):
        job_id = "JID_123456789"
        job_url = "/redfish/v1/Managers/iDRAC.Embedded.1/JID_123456789"
        f_module = self.get_module_mock()
        redfish_response_mock.json_data = {"JobState": "Success"}
        mocker.patch(MODULE_PATH + "redfish_storage_volume.wait_for_job_completion",
                     return_value=(redfish_response_mock, "The job is failed."))
        with pytest.raises(Exception) as exc:
            self.module.track_job(f_module, redfish_connection_mock_for_storage_volume, job_id, job_url)
        assert exc.value.args[0] == "The job is successfully completed."

    def test_validate_negative_job_time_out(self, redfish_default_args):
        redfish_default_args.update({"job_wait": True, "job_wait_timeout": -5})
        f_module = self.get_module_mock(params=redfish_default_args)
        with pytest.raises(Exception) as ex:
            self.module.validate_negative_job_time_out(f_module)
        assert ex.value.args[0] == "The parameter job_wait_timeout value cannot be negative or zero."
