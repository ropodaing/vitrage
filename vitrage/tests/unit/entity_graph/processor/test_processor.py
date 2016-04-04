# Copyright 2015 - Alcatel-Lucent
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import unittest

from oslo_config import cfg

from vitrage.common.constants import EventAction
from vitrage.common.constants import SynchronizerProperties as SyncProps
from vitrage.common.constants import SyncMode
from vitrage.common.constants import VertexProperties as VProps
from vitrage.common.datetime_utils import utcnow
from vitrage.entity_graph.initialization_status import InitializationStatus
from vitrage.entity_graph.processor import processor as proc
from vitrage.entity_graph.states.normalized_resource_state import \
    NormalizedResourceState
import vitrage.graph.utils as graph_utils
from vitrage.synchronizer.plugins.transformer_base import Neighbor
from vitrage.tests.unit.entity_graph.base import TestEntityGraphUnitBase


class TestProcessor(TestEntityGraphUnitBase):

    ZONE_SPEC = 'ZONE_SPEC'
    HOST_SPEC = 'HOST_SPEC'
    INSTANCE_SPEC = 'INSTANCE_SPEC'
    NUM_VERTICES_AFTER_CREATION = 2
    NUM_EDGES_AFTER_CREATION = 1
    NUM_VERTICES_AFTER_DELETION = 1
    NUM_EDGES_AFTER_DELETION = 0

    # noinspection PyAttributeOutsideInit,PyPep8Naming
    @classmethod
    def setUpClass(cls):
        super(TestProcessor, cls).setUpClass()
        cls.conf = cfg.ConfigOpts()
        cls.conf.register_opts(cls.PROCESSOR_OPTS, group='entity_graph')
        cls.conf.register_opts(cls.PLUGINS_OPTS, group='plugins')
        cls.load_plugins(cls.conf)

    # TODO(Alexey): un skip this test when instance transformer update is ready
    @unittest.skip('Not ready yet')
    def test_process_event(self):
        # check create instance event
        processor = proc.Processor(self.conf, InitializationStatus())
        event = self._create_event(spec_type=self.INSTANCE_SPEC,
                                   sync_mode=SyncMode.INIT_SNAPSHOT)
        processor.process_event(event)
        self._check_graph(processor, self.NUM_VERTICES_AFTER_CREATION,
                          self.NUM_EDGES_AFTER_CREATION)

        # check update instance even
        # TODO(Alexey): Create an event in update event structure
        # (update snapshot fields won't work)
        event[SyncProps.SYNC_MODE] = SyncMode.UPDATE
        event[SyncProps.EVENT_TYPE] = 'compute.instance.volume.attach'
        event['hostname'] = 'new_host'
        processor.process_event(event)
        self._check_graph(processor, self.NUM_VERTICES_AFTER_CREATION,
                          self.NUM_EDGES_AFTER_CREATION)

        # check delete instance event
        event[SyncProps.SYNC_MODE] = SyncMode.UPDATE
        event[SyncProps.EVENT_TYPE] = 'compute.instance.delete.end'
        processor.process_event(event)
        self._check_graph(processor, self.NUM_VERTICES_AFTER_DELETION,
                          self.NUM_EDGES_AFTER_DELETION)

    def test_create_entity_with_placeholder_neighbor(self):
        # create instance event with host neighbor and check validity
        self._create_and_check_entity()

    def test_update_entity_state(self):
        # create instance event with host neighbor and check validity
        (vertex, neighbors, processor) =\
            self._create_and_check_entity(status='STARTING')

        # check added entity
        vertex = processor.entity_graph.get_vertex(vertex.vertex_id)
        self.assertEqual('STARTING', vertex.properties[VProps.STATE])

        # update instance event with state running
        vertex.properties[VProps.STATE] = 'RUNNING'
        vertex.properties[VProps.SAMPLE_TIMESTAMP] = str(utcnow())
        processor.update_entity(vertex, neighbors)

        # check state
        self._check_graph(processor, self.NUM_VERTICES_AFTER_CREATION,
                          self.NUM_EDGES_AFTER_CREATION)
        vertex = processor.entity_graph.get_vertex(vertex.vertex_id)
        self.assertEqual('RUNNING', vertex.properties[VProps.STATE])

    def test_change_parent(self):
        # create instance event with host neighbor and check validity
        (vertex, neighbors, processor) = self._create_and_check_entity()

        # update instance event with state running
        (neighbor_vertex, neighbor_edge) = neighbors[0]
        old_neighbor_id = neighbor_vertex.vertex_id
        neighbor_vertex.properties[VProps.ID] = 'newhost-2'
        neighbor_vertex.vertex_id = 'RESOURCE_HOST_newhost-2'
        neighbor_edge.source_id = 'RESOURCE_HOST_newhost-2'
        processor.update_entity(vertex, neighbors)

        # check state
        self._check_graph(processor, self.NUM_VERTICES_AFTER_CREATION,
                          self.NUM_EDGES_AFTER_CREATION)
        neighbor_vertex = \
            processor.entity_graph.get_vertex(old_neighbor_id)
        self.assertIsNone(neighbor_vertex)

    def test_delete_entity(self):
        # create instance event with host neighbor and check validity
        (vertex, neighbors, processor) = self._create_and_check_entity()

        # delete entity
        processor.delete_entity(vertex, neighbors)

        # check deleted entity
        self._check_graph(processor, self.NUM_VERTICES_AFTER_DELETION,
                          self.NUM_EDGES_AFTER_DELETION)
        self.assertTrue(processor.entity_graph.is_vertex_deleted(vertex))

    def test_update_relationship(self):
        # setup
        vertex1, neighbors1, processor = self._create_entity(
            spec_type=self.INSTANCE_SPEC,
            sync_mode=SyncMode.INIT_SNAPSHOT)
        vertex2, neighbors2, processor = self._create_entity(
            spec_type=self.INSTANCE_SPEC,
            sync_mode=SyncMode.INIT_SNAPSHOT,
            processor=processor)
        self.assertEqual(2, processor.entity_graph.num_edges())

        new_edge = graph_utils.create_edge(vertex1.vertex_id,
                                           vertex2.vertex_id,
                                           'backup')
        new_neighbors = [Neighbor(None, new_edge)]

        # action
        processor.update_relationship(None, new_neighbors)

        # test assertions
        self.assertEqual(3, processor.entity_graph.num_edges())

    def test_delete_relationship(self):
        # setup
        vertex1, neighbors1, processor = self._create_entity(
            spec_type=self.INSTANCE_SPEC,
            sync_mode=SyncMode.INIT_SNAPSHOT)
        vertex2, neighbors2, processor = self._create_entity(
            spec_type=self.INSTANCE_SPEC,
            sync_mode=SyncMode.INIT_SNAPSHOT,
            processor=processor)
        self.assertEqual(2, processor.entity_graph.num_edges())

        new_edge = graph_utils.create_edge(vertex1.vertex_id,
                                           vertex2.vertex_id,
                                           'backup')
        processor.entity_graph.add_edge(new_edge)
        self.assertEqual(3, processor.entity_graph.num_edges())
        new_neighbors = [Neighbor(None, new_edge)]

        # action
        processor.delete_relationship(None, new_neighbors)

        # test assertions
        self.assertEqual(2, processor.entity_graph.num_edges())

    def test_update_neighbors(self):
        # create instance event with host neighbor and check validity
        (vertex, neighbors, processor) = self._create_and_check_entity()

        # update instance event with state running
        (neighbor_vertex, neighbor_edge) = neighbors[0]
        old_neighbor_id = neighbor_vertex.vertex_id
        neighbor_vertex.properties[VProps.ID] = 'newhost-2'
        neighbor_vertex.vertex_id = 'RESOURCE_HOST_newhost-2'
        neighbor_edge.source_id = 'RESOURCE_HOST_newhost-2'
        processor._update_neighbors(vertex, neighbors)

        # check state
        self._check_graph(processor, self.NUM_VERTICES_AFTER_CREATION,
                          self.NUM_EDGES_AFTER_CREATION)
        self.assertIsNone(processor.entity_graph.get_vertex(old_neighbor_id))

        # update instance with the same neighbor
        processor._update_neighbors(vertex, neighbors)

        # check state
        self._check_graph(processor, self.NUM_VERTICES_AFTER_CREATION,
                          self.NUM_EDGES_AFTER_CREATION)

    def test_delete_old_connections(self):
        # create instance event with host neighbor and check validity
        (vertex, neighbors, processor) = self._create_and_check_entity()

        # delete entity
        processor._delete_old_connections(vertex, [neighbors[0][1]])

        # check deleted entity
        self._check_graph(processor,
                          self.NUM_VERTICES_AFTER_DELETION,
                          self.NUM_EDGES_AFTER_DELETION)

    def test_calculate_aggregated_state(self):
        # setup
        instances = []
        for i in range(6):
            (vertex, neighbors, processor) = self._create_and_check_entity()
            instances.append((vertex, processor))

        # action
        # state already exists and its updated
        instances[0][0][VProps.STATE] = 'SUSPENDED'
        instances[0][1]._calculate_aggregated_state(instances[0][0],
                                                    EventAction.UPDATE_ENTITY)

        # vitrage state doesn't exist and its updated
        instances[1][0][VProps.STATE] = None
        instances[1][1].entity_graph.update_vertex(instances[1][0])
        instances[1][0][VProps.VITRAGE_STATE] = 'SUBOPTIMAL'
        instances[1][1]._calculate_aggregated_state(instances[1][0],
                                                    EventAction.UPDATE_ENTITY)

        # state exists and vitrage state changes
        instances[2][0][VProps.VITRAGE_STATE] = 'SUBOPTIMAL'
        instances[2][1]._calculate_aggregated_state(instances[2][0],
                                                    EventAction.UPDATE_ENTITY)

        # vitrage state exists and state changes
        instances[3][0][VProps.STATE] = None
        instances[3][0][VProps.VITRAGE_STATE] = 'SUBOPTIMAL'
        instances[3][1].entity_graph.update_vertex(instances[3][0])
        instances[3][0][VProps.STATE] = 'SUSPENDED'
        instances[3][1]._calculate_aggregated_state(instances[3][0],
                                                    EventAction.UPDATE_ENTITY)

        # state and vitrage state exists and state changes
        instances[4][0][VProps.VITRAGE_STATE] = 'SUBOPTIMAL'
        instances[4][1].entity_graph.update_vertex(instances[4][0])
        instances[4][0][VProps.STATE] = 'SUSPENDED'
        instances[4][1]._calculate_aggregated_state(instances[4][0],
                                                    EventAction.UPDATE_ENTITY)

        # state and vitrage state exists and vitrage state changes
        instances[5][0][VProps.VITRAGE_STATE] = 'SUBOPTIMAL'
        instances[5][1].entity_graph.update_vertex(instances[5][0])
        instances[5][1]._calculate_aggregated_state(instances[5][0],
                                                    EventAction.UPDATE_ENTITY)

        # test assertions
        self.assertEqual(NormalizedResourceState.SUSPENDED,
                         instances[0][0][VProps.AGGREGATED_STATE])
        self.assertEqual(NormalizedResourceState.SUBOPTIMAL,
                         instances[1][0][VProps.AGGREGATED_STATE])
        self.assertEqual(NormalizedResourceState.SUBOPTIMAL,
                         instances[2][0][VProps.AGGREGATED_STATE])
        self.assertEqual(NormalizedResourceState.SUSPENDED,
                         instances[3][0][VProps.AGGREGATED_STATE])
        self.assertEqual(NormalizedResourceState.SUSPENDED,
                         instances[4][0][VProps.AGGREGATED_STATE])
        self.assertEqual(NormalizedResourceState.SUBOPTIMAL,
                         instances[5][0][VProps.AGGREGATED_STATE])

    def _create_and_check_entity(self, processor=None, **kwargs):
        # create instance event with host neighbor
        (vertex, neighbors, processor) = self._create_entity(
            spec_type=self.INSTANCE_SPEC,
            sync_mode=SyncMode.INIT_SNAPSHOT,
            properties=kwargs,
            processor=processor)

        # check the data in the graph is correct
        self._check_graph(processor,
                          self.NUM_VERTICES_AFTER_CREATION,
                          self.NUM_EDGES_AFTER_CREATION)

        return vertex, neighbors, processor

    def _check_graph(self, processor, num_vertices, num_edges):
        self.assertEqual(num_vertices, len(processor.entity_graph))
        self.assertEqual(num_edges, processor.entity_graph.num_edges())
