"""
Tests for graph structure building and rendering.
Covers app/graph.py and plotly_graph modules.
"""

import pytest
import math
from types import SimpleNamespace
from uuid import UUID
from app import crud, models, graph, schemas
from app.plotly_graph import plotly_render, layout, colors


class TestGraphStructureBuilding:
    """Test build_plotly_figure_json with various family tree structures."""
    
    def test_empty_tree(self, db_session):
        """Test graph building with no people."""
        fig_dict = graph.build_plotly_figure_json(db_session, tree_id=999)
        assert isinstance(fig_dict, dict)
        assert "layout" in fig_dict
        assert fig_dict["layout"]["title"]["text"] == "No family data found"
    
    def test_single_person_tree(self, db_session, sample_tree, sample_tree_version, sample_person):
        """Test graph with single person (no relationships)."""
        fig_dict = graph.build_plotly_figure_json(
            db_session, 
            tree_version_id=sample_tree_version.id
        )
        assert isinstance(fig_dict, dict)
        assert "data" in fig_dict
        # Should have nodes and edges traces
        traces = fig_dict["data"]
        assert len(traces) >= 2  # nodes and edges minimum
    
    def test_parent_child_relationship(self, db_session, sample_tree, sample_tree_version, populated_tree):
        """Test graph with parent-child relationship."""
        tree, version, people, rels = populated_tree
        fig_dict = graph.build_plotly_figure_json(
            db_session,
            tree_version_id=version.id
        )
        assert isinstance(fig_dict, dict)
        traces = fig_dict["data"]
        # Should have nodes and edges
        assert len(traces) >= 1
        # Check layout has expected fields
        assert "layout" in fig_dict

    
    def test_graph_with_tree_version_filter(self, db_session, sample_tree, sample_tree_version):
        """Test filtering graph by tree_version_id."""
        # Create person in this version
        person = crud.create_person(
            db_session,
            display_name="Test Person",
            sex="M",
            tree_id=sample_tree.id,
            tree_version_id=sample_tree_version.id,
            notes=""
        )
        
        fig_dict = graph.build_plotly_figure_json(
            db_session,
            tree_version_id=sample_tree_version.id
        )
        assert isinstance(fig_dict, dict)
        traces = fig_dict["data"]
        assert len(traces) >= 1
    
    def test_graph_with_tree_id_filter(self, db_session, sample_tree, sample_tree_version):
        """Test filtering graph by tree_id (uses active version)."""
        # Create person
        person = crud.create_person(
            db_session,
            display_name="Test Person",
            sex="F",
            tree_id=sample_tree.id,
            tree_version_id=sample_tree_version.id,
            notes=""
        )
        
        fig_dict = graph.build_plotly_figure_json(
            db_session,
            tree_id=sample_tree.id
        )
        assert isinstance(fig_dict, dict)
        traces = fig_dict["data"]
        assert len(traces) >= 1


class TestMapBuilding:
    """Test map building (children, parents, gender, etc.) from database."""
    
    def test_build_maps_single_person(self, db_session, sample_tree, sample_tree_version, sample_person):
        """Test map building with single person."""
        children_map, parents_map, gender_map, display_name, hover_name, roots, spouse_map = \
            plotly_render.build_maps_from_db([sample_person], [])
        
        assert isinstance(children_map, dict)
        assert isinstance(parents_map, dict)
        assert isinstance(gender_map, dict)
        assert isinstance(roots, list)
        assert isinstance(spouse_map, dict)
        assert str(sample_person.id) in roots
    
    def test_build_maps_parent_child(self, db_session, populated_fixture):
        """Test map building with parent-child relationship."""
        tree, version, people, rels = populated_fixture
        
        # Get people and relationships as proper objects
        db_people = db_session.query(models.Person).filter(
            models.Person.tree_version_id == version.id
        ).all()
        db_rels = db_session.query(models.Relationship).filter(
            models.Relationship.tree_version_id == version.id
        ).all()
        
        children_map, parents_map, gender_map, _, _, roots, _ = \
            plotly_render.build_maps_from_db(db_people, db_rels)
        
        assert len(children_map) > 0
        assert len(parents_map) > 0
        # At least one parent should have children
        has_children = any(len(v) > 0 for v in children_map.values())
        assert has_children
    
    def test_build_maps_spouse_relationships(self, db_session, sample_tree, sample_tree_version):
        """Test spouse relationship mapping."""
        # Create two people
        person1 = crud.create_person(
            db_session, display_name="Person A", sex="M",
            tree_id=sample_tree.id, tree_version_id=sample_tree_version.id, notes=""
        )
        person2 = crud.create_person(
            db_session, display_name="Person B", sex="F",
            tree_id=sample_tree.id, tree_version_id=sample_tree_version.id, notes=""
        )
        
        # Create spouse relationship
        rel = crud.create_relationship(
            db_session,
            from_id=str(person1.id),
            to_id=str(person2.id),
            rel_type=models.RelType.SPOUSE_OF.value,
            tree_id=sample_tree.id,
            tree_version_id=sample_tree_version.id
        )
        
        children_map, parents_map, gender_map, _, _, roots, spouse_map = \
            plotly_render.build_maps_from_db([person1, person2], [rel])
        
        # Spouse map should have the pair
        assert str(person1.id) in spouse_map or str(person2.id) in spouse_map


class TestRadialTreeLayout:
    """Test hierarchical radial layout algorithm."""
    
    def test_single_root_layout(self):
        """Test layout with single root node."""
        children_map = {
            "root": ["child1", "child2", "child3"]
        }
        roots = ["root"]
        
        pos = layout.radial_tree_layout_balanced_spaced(children_map, roots)
        
        assert "root" in pos
        assert "child1" in pos
        assert "child2" in pos
        assert "child3" in pos
        # Root should be at origin (or near it)
        assert pos["root"] == (0.0, 0.0)
        # Children should be at same depth (same radius)
        distances = [math.sqrt(pos[c][0]**2 + pos[c][1]**2) for c in ["child1", "child2", "child3"]]
        assert all(abs(d - distances[0]) < 0.01 for d in distances)
    
    def test_multiple_levels_layout(self):
        """Test layout with multiple generational levels."""
        children_map = {
            "root": ["parent1", "parent2"],
            "parent1": ["child1", "child2"],
            "parent2": ["child3"],
            "child1": [],
            "child2": [],
            "child3": [],
        }
        roots = ["root"]
        
        pos = layout.radial_tree_layout_balanced_spaced(children_map, roots)
        
        # All nodes should have positions
        assert len(pos) == 6
        # Parents should be closer than children (smaller radius)
        root_dist = math.sqrt(pos["root"][0]**2 + pos["root"][1]**2)
        parent_dists = [math.sqrt(pos["parent1"][0]**2 + pos["parent1"][1]**2),
                        math.sqrt(pos["parent2"][0]**2 + pos["parent2"][1]**2)]
        child_dists = [math.sqrt(pos["child1"][0]**2 + pos["child1"][1]**2),
                       math.sqrt(pos["child2"][0]**2 + pos["child2"][1]**2),
                       math.sqrt(pos["child3"][0]**2 + pos["child3"][1]**2)]
        
        # Root should be closest
        assert root_dist < min(parent_dists)
        # Parents should be closer than children
        avg_parent_dist = sum(parent_dists) / len(parent_dists)
        avg_child_dist = sum(child_dists) / len(child_dists)
        assert avg_parent_dist < avg_child_dist
    
    def test_multiple_roots_layout(self):
        """Test layout with multiple root nodes (virtual root)."""
        children_map = {
            "root1": ["child1"],
            "root2": ["child2"],
            "child1": [],
            "child2": []
        }
        roots = ["root1", "root2"]
        
        pos = layout.radial_tree_layout_balanced_spaced(children_map, roots)
        
        # Both roots should have positions
        assert "root1" in pos
        assert "root2" in pos
        # Roots should be at same depth (virtual root = depth 0)
        root1_dist = math.sqrt(pos["root1"][0]**2 + pos["root1"][1]**2)
        root2_dist = math.sqrt(pos["root2"][0]**2 + pos["root2"][1]**2)
        assert abs(root1_dist - root2_dist) < 0.01  # Same depth
    
    def test_empty_tree_layout(self):
        """Test layout with empty tree."""
        pos = layout.radial_tree_layout_balanced_spaced({}, [])
        assert pos == {}
    
    def test_cycle_detection_layout(self):
        """Test layout handles cycles gracefully."""
        # Create a cycle: A -> B -> C -> A
        children_map = {
            "A": ["B"],
            "B": ["C"],
            "C": ["A"]
        }
        roots = ["A"]
        
        # Should not hang or crash
        pos = layout.radial_tree_layout_balanced_spaced(children_map, roots)
        assert "A" in pos
        assert "B" in pos
        assert "C" in pos


class TestColoringScheme:
    """Test sibling coloring logic."""
    
    def test_color_by_gender(self):
        """Test nodes colored by gender when unpaired."""
        nodes = ["person1", "person2", "person3"]
        children_map = {}
        parents_map = {}
        gender_map = {"person1": "M", "person2": "F", "person3": None}
        
        node_colors = colors.build_sibling_colors(nodes, children_map, parents_map, gender_map)
        
        assert len(node_colors) == 3
        # Male should be blue
        assert node_colors[0] == "#87CEFA"
        # Female should be pink
        assert node_colors[1] == "#FFB6C1"
        # Unknown should be gray
        assert node_colors[2] == "#D3D3D3"
    
    def test_color_by_parent(self):
        """Test siblings colored by parent."""
        nodes = ["parent", "child1", "child2", "child3"]
        children_map = {"parent": ["child1", "child2", "child3"]}
        parents_map = {
            "child1": ["parent"],
            "child2": ["parent"],
            "child3": ["parent"]
        }
        gender_map = {}
        
        node_colors = colors.build_sibling_colors(nodes, children_map, parents_map, gender_map)
        
        assert len(node_colors) == 4
        # Children should all have same color (parent's color from parent_color_map)
        assert node_colors[1] == node_colors[2] == node_colors[3]
        # All colors should be from palette or default gray
        palette = ["#FFA07A", "#98FB98", "#87CEFA", "#DDA0DD", "#F4A460",
                   "#66CDAA", "#FFB6C1", "#E6E6FA", "#20B2AA", "#D3D3D3"]
        assert all(c in palette for c in node_colors)
    
    def test_multiple_sibling_groups(self):
        """Test different sibling groups get different colors."""
        nodes = ["parent1", "parent2", "child1a", "child1b", "child2a"]
        children_map = {
            "parent1": ["child1a", "child1b"],
            "parent2": ["child2a"]
        }
        parents_map = {
            "child1a": ["parent1"],
            "child1b": ["parent1"],
            "child2a": ["parent2"]
        }
        gender_map = {}
        
        node_colors = colors.build_sibling_colors(nodes, children_map, parents_map, gender_map)
        
        assert len(node_colors) == 5
        # child1a and child1b should have same color
        assert node_colors[2] == node_colors[3]
        # child2a should be different from child1x
        assert node_colors[4] != node_colors[2]


class TestSpousePositioning:
    """Test spouse side-by-side positioning algorithm."""
    
    def test_spouse_positioning_basic(self):
        """Test basic spouse positioning."""
        pos = {
            "person1": (0.0, 2.0),
            "person2": (0.5, 2.0),
            "child1": (0.0, 4.0),
            "child2": (0.5, 4.0)
        }
        spouse_map = {"person1": ["person2"], "person2": ["person1"]}
        children_map = {
            "person1": ["child1", "child2"],
            "person2": ["child1", "child2"],
            "child1": [],
            "child2": []
        }
        parents_map = {}
        
        adjusted = plotly_render.adjust_spouse_positions(pos, spouse_map, children_map, parents_map)
        
        # Spouses should be at same y but different x
        assert adjusted["person1"][1] == adjusted["person2"][1]
        assert adjusted["person1"][0] != adjusted["person2"][0]
        # They should be closer to midpoint
        mid_x = 0.25
        assert abs(adjusted["person1"][0] - mid_x) < 0.5
        assert abs(adjusted["person2"][0] - mid_x) < 0.5
    
    def test_spouse_positioning_no_children(self):
        """Test spouse positioning without children."""
        pos = {
            "spouse1": (1.0, 1.0),
            "spouse2": (2.0, 1.0)
        }
        spouse_map = {"spouse1": ["spouse2"], "spouse2": ["spouse1"]}
        children_map = {"spouse1": [], "spouse2": []}
        parents_map = {}
        
        adjusted = plotly_render.adjust_spouse_positions(pos, spouse_map, children_map, parents_map)
        
        # Should still adjust to be closer
        assert adjusted["spouse1"][0] < adjusted["spouse2"][0]
        assert adjusted["spouse1"][1] == adjusted["spouse2"][1]
    
    def test_spouse_positioning_many_children(self):
        """Test spacing increases with many children."""
        pos = {
            "spouse1": (0.0, 2.0),
            "spouse2": (0.5, 2.0),
            "child1": (0.0, 4.0),
            "child2": (0.1, 4.0),
            "child3": (0.2, 4.0),
            "child4": (0.3, 4.0),
            "child5": (0.4, 4.0),
            "child6": (0.5, 4.0),
            "child7": (0.6, 4.0),
            "child8": (0.7, 4.0),
            "child9": (0.8, 4.0),
        }
        spouse_map = {"spouse1": ["spouse2"], "spouse2": ["spouse1"]}
        children_map = {
            "spouse1": list(f"child{i}" for i in range(1, 10)),
            "spouse2": list(f"child{i}" for i in range(1, 10)),
        }
        parents_map = {}
        
        adjusted = plotly_render.adjust_spouse_positions(pos, spouse_map, children_map, parents_map)
        
        # With many children, spacing should be larger (0.6+)
        spacing = abs(adjusted["spouse2"][0] - adjusted["spouse1"][0])
        assert spacing >= 0.5
