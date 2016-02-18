# Copyright 2016 Nokia
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import testtools

from vitrage.entity_graph.initialization_status import InitializationStatus
from vitrage.entity_graph.processor import processor as proc
from vitrage.tests.mocks import mock_syncronizer as mock_sync


class BaseMock(testtools.TestCase):
    """Base test class for Vitrage API tests."""

    def create_processor_with_graph(self):
        events = self._create_mock_events()
        processor = proc.Processor(InitializationStatus())

        for event in events:
            processor.process_event(event)

        return processor

    @staticmethod
    def _create_mock_events():
        gen_list = mock_sync.simple_zone_generators(
            2, 4, snapshot_events=2, snap_vals={'sync_mode': 'init_snapshot'})
        gen_list += mock_sync.simple_host_generators(
            2, 4, 4, snap_vals={'sync_mode': 'init_snapshot'})
        gen_list += mock_sync.simple_instance_generators(
            4, 15, 15, snap_vals={'sync_mode': 'init_snapshot'})
        return mock_sync.generate_sequential_events_list(gen_list)
