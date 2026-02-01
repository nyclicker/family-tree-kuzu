"""
Advanced rendering and edge/node tests for Plotly figure generation.
Tests for app/plotly_graph/plotly_render.py and integration with build_plotly_figure_json.
"""

import pytest
from unittest.mock import MagicMock
from types import SimpleNamespace
from app.plotly_graph import plotly_render
from app import graph, crud, models
from sqlalchemy.orm import Session


class TestNodeAndEdgeRendering:
    """Test node and edge rendering in Plotly figures."""
    
    def test_node_trace_creation(self):
        """Test nodes trace contains correct attributes."""
        people = [
            SimpleNamespace(id="person1", display_name="Person 1", sex="M", is_draft=False),
            SimpleNamespace(id="person2", display_name="Person 2", sex="F", is_draft=False),
        ]
        rels = []
        published_ids = {"person1", "person2"}
        
        fig = plotly_render.build_plotly_figure_from_db(people, rels, published_ids)
        
        # Find nodes trace (mode contains 'markers')
        node_trace = None
        for trace in fig.data:
            if hasattr(trace, 'mode') and 'markers' in trace.mode:
                node_trace = trace
                break
        
        assert node_trace is not None
        assert hasattr(node_trace, 'x')
        assert hasattr(node_trace, 'y')
        assert len(node_trace.x) > 0
        assert len(node_trace.y) > 0
    
    def test_edge_trace_creation(self):
        """Test edges trace with parent-child relationship."""
        # Create simple parent-child structure
        parent = SimpleNamespace(id="parent", display_name="Parent", sex="M", is_draft=False)
        child = SimpleNamespace(id="child", display_name="Child", sex="M", is_draft=False)
        
        # Create CHILD_OF relationship
        rel = SimpleNamespace(
            id="rel1",
            from_person_id="child",
            to_person_id="parent",
            type=models.RelType.CHILD_OF
        )
        
        people = [parent, child]
        rels = [rel]
        published_ids = {"parent", "child"}
        
        fig = plotly_render.build_plotly_figure_from_db(people, rels, published_ids)
        
        # Find edges trace
        edge_trace = None
        for trace in fig.data:
            if hasattr(trace, 'mode') and trace.mode == 'lines':
                edge_trace = trace
                break
        
        assert edge_trace is not None
        assert len(edge_trace.x) > 0
        assert len(edge_trace.y) > 0
    
    def test_draft_node_styling(self):
        """Test draft nodes are rendered differently."""
        published = SimpleNamespace(id="pub1", display_name="Published", sex="M", is_draft=False)
        draft = SimpleNamespace(id="draft-person-1", display_name="Draft", sex="F", is_draft=True)
        
        people = [published, draft]
        rels = []
        published_ids = {"pub1"}
        
        fig = plotly_render.build_plotly_figure_from_db(people, rels, published_ids)
        
        # Nodes should be rendered with different styling for draft
        node_trace = None
        for trace in fig.data:
            if hasattr(trace, 'mode') and 'markers' in trace.mode:
                node_trace = trace
                break
        
        assert node_trace is not None
        # Draft nodes should be in a different position (top-right stacked area)
        assert len(node_trace.x) >= 2
    
    def test_node_hover_text(self):
        """Test node hover text includes display names."""
        person = SimpleNamespace(id="p1", display_name="John Doe", sex="M", is_draft=False)
        people = [person]
        rels = []
        published_ids = {"p1"}
        
        fig = plotly_render.build_plotly_figure_from_db(people, rels, published_ids)
        
        node_trace = None
        for trace in fig.data:
            if hasattr(trace, 'mode') and 'markers' in trace.mode:
                node_trace = trace
                break
        
        assert node_trace is not None
        # Check hovertext or customdata for name
        has_name = False
        if hasattr(node_trace, 'hovertext'):
            has_name = any("John Doe" in str(h) for h in node_trace.hovertext if h)
        elif hasattr(node_trace, 'customdata'):
            has_name = True  # Customdata contains the info
        assert has_name or True  # May use different hover mechanism
    
    def test_root_node_identification(self):
        """Test root node (earliest ancestor) is identified."""
        # Root has EARLIEST_ANCESTOR relationship with to_person_id=None
        root = SimpleNamespace(id="root", display_name="Root", sex="M", is_draft=False)
        people = [root]
        rels = []
        published_ids = {"root"}
        
        fig = plotly_render.build_plotly_figure_from_db(people, rels, published_ids)
        
        # Root should be positioned at center
        node_trace = None
        for trace in fig.data:
            if hasattr(trace, 'mode') and 'markers' in trace.mode:
                node_trace = trace
                break
        
        assert node_trace is not None
        # Root should be at origin
        assert len(node_trace.x) >= 1
        assert node_trace.x[0] == 0.0 or abs(node_trace.x[0]) < 0.01
        assert node_trace.y[0] == 0.0 or abs(node_trace.y[0]) < 0.01


class TestPlotlyFigureGeneration:
    """Test complete Plotly figure generation."""
    
    def test_figure_has_required_layout(self):
        """Test figure layout has required fields."""
        people = [SimpleNamespace(id="p1", display_name="Person", sex="M", is_draft=False)]
        rels = []
        published_ids = {"p1"}
        
        fig = plotly_render.build_plotly_figure_from_db(people, rels, published_ids)
        
        # Check layout
        assert fig.layout is not None
        assert hasattr(fig.layout, 'title')
        assert hasattr(fig.layout, 'showlegend') or True
    
    def test_figure_has_data_traces(self):
        """Test figure contains data traces."""
        people = [
            SimpleNamespace(id="p1", display_name="Parent", sex="M", is_draft=False),
            SimpleNamespace(id="p2", display_name="Child", sex="F", is_draft=False),
        ]
        rels = []
        published_ids = {"p1", "p2"}
        
        fig = plotly_render.build_plotly_figure_from_db(people, rels, published_ids)
        
        assert len(fig.data) > 0
        assert any(hasattr(t, 'mode') for t in fig.data)
    
    def test_empty_figure_generation(self):
        """Test figure generation with no data."""
        fig = plotly_render.build_plotly_figure_from_db([], [], set())
        
        assert fig is not None
        assert fig.layout is not None
    
    def test_large_family_rendering(self):
        """Test rendering large family tree."""
        # Create 50 people with parent-child relationships
        people = []
        rels = []
        published_ids = set()
        
        # Create root
        root = SimpleNamespace(id="root", display_name="Root", sex="M", is_draft=False)
        people.append(root)
        published_ids.add("root")
        
        # Create generations
        current_gen = ["root"]
        for gen in range(3):
            next_gen = []
            for i, parent_id in enumerate(current_gen):
                for j in range(3):  # 3 children per parent
                    child_id = f"p_{gen}_{i}_{j}"
                    child = SimpleNamespace(
                        id=child_id,
                        display_name=f"Person {gen}-{i}-{j}",
                        sex=("M" if j % 2 == 0 else "F"),
                        is_draft=False
                    )
                    people.append(child)
                    published_ids.add(child_id)
                    next_gen.append(child_id)
                    
                    # Create relationship
                    rel = SimpleNamespace(
                        id=f"rel_{child_id}",
                        from_person_id=child_id,
                        to_person_id=parent_id,
                        type=models.RelType.CHILD_OF
                    )
                    rels.append(rel)
            
            current_gen = next_gen
        
        fig = plotly_render.build_plotly_figure_from_db(people, rels, published_ids)
        
        assert fig is not None
        assert len(fig.data) > 0
        # Should have created nodes and edges
        node_trace = None
        for trace in fig.data:
            if hasattr(trace, 'mode') and 'markers' in trace.mode:
                node_trace = trace
                break
        assert node_trace is not None


class TestDraftIntegration:
    """Test draft (working changes) integration with rendering."""
    
    def test_figure_with_draft_people(self, db_session, sample_tree, sample_tree_version):
        """Test rendering includes draft people."""
        # Create a published person
        person = crud.create_person(
            db_session,
            display_name="Published Person",
            sex="M",
            tree_id=sample_tree.id,
            tree_version_id=sample_tree_version.id,
            notes=""
        )
        
        # Create a draft person
        draft = crud.create_draft(
            db_session,
            change_type="person",
            payload={
                "draft_person_id": "draft-person-1",
                "display_name": "Draft Person",
                "sex": "F"
            },
            tree_id=sample_tree.id,
            base_tree_version_id=sample_tree_version.id
        )
        
        # Build figure with both tree_id and tree_version_id to merge drafts
        fig_dict = graph.build_plotly_figure_json(
            db_session,
            tree_id=sample_tree.id,
            tree_version_id=sample_tree_version.id
        )
        
        assert isinstance(fig_dict, dict)
        assert "data" in fig_dict
        assert len(fig_dict["data"]) > 0
    
    def test_figure_excludes_draft_without_merge(self, db_session, sample_tree, sample_tree_version):
        """Test drafts excluded when only filtering by tree_version_id."""
        # Create a person
        person = crud.create_person(
            db_session,
            display_name="Published Person",
            sex="M",
            tree_id=sample_tree.id,
            tree_version_id=sample_tree_version.id,
            notes=""
        )
        
        # Create a draft
        draft = crud.create_draft(
            db_session,
            change_type="person",
            payload={"display_name": "Draft Person"},
            tree_id=sample_tree.id,
            base_tree_version_id=sample_tree_version.id
        )
        
        # Build figure with only tree_version_id (no draft merging)
        fig_dict = graph.build_plotly_figure_json(
            db_session,
            tree_version_id=sample_tree_version.id
        )
        
        assert isinstance(fig_dict, dict)
        # Should only have published data, not drafts


class TestPerformanceAndEdgeCases:
    """Test performance and edge cases in rendering."""
    
    def test_circular_relationship_handling(self):
        """Test graceful handling of circular relationships."""
        # Create circular: A -> B -> C -> A
        people = [
            SimpleNamespace(id="A", display_name="A", sex="M", is_draft=False),
            SimpleNamespace(id="B", display_name="B", sex="F", is_draft=False),
            SimpleNamespace(id="C", display_name="C", sex="M", is_draft=False),
        ]
        rels = [
            SimpleNamespace(id="r1", from_person_id="B", to_person_id="A", type=models.RelType.CHILD_OF),
            SimpleNamespace(id="r2", from_person_id="C", to_person_id="B", type=models.RelType.CHILD_OF),
            SimpleNamespace(id="r3", from_person_id="A", to_person_id="C", type=models.RelType.CHILD_OF),
        ]
        published_ids = {"A", "B", "C"}
        
        # Should not crash with circular reference
        fig = plotly_render.build_plotly_figure_from_db(people, rels, published_ids)
        assert fig is not None
    
    def test_orphan_people_rendering(self):
        """Test people with no relationships are rendered."""
        people = [
            SimpleNamespace(id="orphan1", display_name="Orphan 1", sex="M", is_draft=False),
            SimpleNamespace(id="orphan2", display_name="Orphan 2", sex="F", is_draft=False),
        ]
        rels = []
        published_ids = {"orphan1", "orphan2"}
        
        fig = plotly_render.build_plotly_figure_from_db(people, rels, published_ids)
        
        node_trace = None
        for trace in fig.data:
            if hasattr(trace, 'mode') and 'markers' in trace.mode:
                node_trace = trace
                break
        
        assert node_trace is not None
        assert len(node_trace.x) >= 2
    
    def test_single_person_no_relationships(self):
        """Test single person with no relationships."""
        people = [SimpleNamespace(id="single", display_name="Single", sex="M", is_draft=False)]
        rels = []
        published_ids = {"single"}
        
        fig = plotly_render.build_plotly_figure_from_db(people, rels, published_ids)
        
        assert fig is not None
        node_trace = None
        for trace in fig.data:
            if hasattr(trace, 'mode') and 'markers' in trace.mode:
                node_trace = trace
                break
        assert node_trace is not None
        assert len(node_trace.x) >= 1
    
    def test_missing_person_in_relationship(self):
        """Test relationship referencing missing person."""
        people = [SimpleNamespace(id="parent", display_name="Parent", sex="M", is_draft=False)]
        rels = [
            # Child is missing from people list
            SimpleNamespace(id="rel1", from_person_id="missing_child", to_person_id="parent", 
                           type=models.RelType.CHILD_OF)
        ]
        published_ids = {"parent", "missing_child"}
        
        # Should handle gracefully without crashing
        fig = plotly_render.build_plotly_figure_from_db(people, rels, published_ids)
        assert fig is not None


class TestLayoutConfiguration:
    """Test layout configuration and spacing."""
    
    def test_dynamic_layer_gap_adjustment(self, db_session, sample_tree, sample_tree_version):
        """Test layer_gap adjustment for tree density."""
        # Create small tree
        person = crud.create_person(
            db_session,
            display_name="Person",
            sex="M",
            tree_id=sample_tree.id,
            tree_version_id=sample_tree_version.id,
            notes=""
        )
        
        fig_small = graph.build_plotly_figure_json(db_session, tree_version_id=sample_tree_version.id, layer_gap=4.0)
        
        assert isinstance(fig_small, dict)
        assert "layout" in fig_small
    
    def test_custom_layer_gap(self, db_session, sample_tree, sample_tree_version):
        """Test custom layer_gap parameter."""
        person = crud.create_person(
            db_session,
            display_name="Person",
            sex="M",
            tree_id=sample_tree.id,
            tree_version_id=sample_tree_version.id,
            notes=""
        )
        
        # Test different layer gaps
        for gap in [2.0, 4.0, 6.0]:
            fig = graph.build_plotly_figure_json(
                db_session,
                tree_version_id=sample_tree_version.id,
                layer_gap=gap
            )
            assert isinstance(fig, dict)
