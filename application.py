
import sys
from collections import deque

from PySide6.QtCore import QRectF, Qt, QLineF, QPointF
from PySide6.QtGui import QAction, QKeySequence, QPainter, QPen, QColor, QBrush, QPolygonF, QPainterPath, QPainterPathStroker
from PySide6.QtWidgets import QMainWindow, QApplication, QGraphicsScene, QGraphicsView, QGraphicsObject, QGraphicsItem, QStyleOptionGraphicsItem, QWidget

import numpy as np
import copy
import math

import main

class Vertex(QGraphicsObject):
    def __init__(self, window, id, x_coord, y_coord, radius = 25, subgraph = 0, displayed = False, id_visible = True) -> None:
        super().__init__()

        self.window = window
        self.__name__ = 'Vertex'
        self.id = id
        self.radius = radius
        self.x_coord = x_coord
        self.y_coord = y_coord
        self.subgraph = subgraph
        
        self.color = "#f3f6f4"
        self.id_visible = id_visible

        self.displayed = displayed
        if self.displayed == True:
            self.setZValue(1)
        else:
            self.setZValue(-5)

        self.edges = []
        
        self.setPos(x_coord,y_coord)

        self.canMove = True        # default behavior for mouse dragging
        self.setFlag(QGraphicsItem.ItemIsMovable, enabled = self.canMove)

        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
    
    def mouseReleaseEvent(self, event):
        QGraphicsItem.mouseReleaseEvent(self, event)
        
        x = self.pos().x()
        y = self.pos().y()

        self.x_coord = x
        self.y_coord = -y

        self.window.update_node_position(self.id, self.x_coord, self.y_coord, index = self.subgraph)

        self.window.scene.update()

        #print("dragged node",self.id,"to position",self.x_coord,self.y_coord)

        if self.window.dynamic_forces == True and self.window.layout in ["force bfs", "force random", "force custom"]:
            self.window.layout = "force custom"
            print("updating force layout")
            self.window.regenerate()
        
    def toggleVisibility(self):
        if self.displayed == True:
            self.displayed = False
            self.setZValue(-5)
        else:
            self.displayed = True
            self.setZValue(1)
        self.updateEdgeVisibility()

    def turnVisible(self, edge_update = True):
        self.displayed = True
        self.setZValue(1)
        if edge_update:
            self.updateEdgeVisibility()
        
    def updateEdgeVisibility(self):
        for edge in self.edges:
            if edge[1].displayed and self.displayed:
                edge[0].displayed = True
            else:
                edge[0].displayed = False


    def moveVertex(self, x, y):
        if main.printing_mode:
            print("node", self.id, "is currently at", self.pos())
            print("moving node",self.id,"from",self.x_coord,self.y_coord,"to",x,y)
            
        #print("moving node",self.id,"from",self.x_coord,self.y_coord,"to",x,y)
        
        self.setPos(x, y)
        self.x_coord = x
        self.y_coord = -y
        self.update_edges()

    def addEdge(self, edge_tuple):          # format (edge object, other vertex object)
        self.edges.append(edge_tuple)
        edge_tuple[0].displayed = self.displayed

    def physical_location(self) -> QRectF:
        return QRectF(self.x_coord, -self.y_coord, self.radius*2, self.radius*2)
        
    def boundingRect(self) -> QRectF:
        return QRectF(0,0,self.radius*2,self.radius*2)        


    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget = None):
        if self.displayed:
            painter.setRenderHints(QPainter.Antialiasing)
            painter.setPen(
                QPen(
                    QColor(self.color).darker(),
                    2,
                    Qt.SolidLine,
                    Qt.RoundCap,
                    Qt.RoundJoin,
                )
            )
            painter.setBrush(QBrush(QColor(self.color)))
            painter.drawEllipse(self.boundingRect())
            painter.setPen(QPen(QColor("black")))
            if self.id_visible:
                painter.drawText(self.boundingRect(), Qt.AlignCenter, self.id)


    def toggle_movability(self):
        self.canMove = not self.canMove
        self.setFlag(QGraphicsItem.ItemIsMovable, enabled = self.canMove)

    def toggle_id_visibility(self):
        self.id_visible = not self.id_visible
        
        
    def update_edges(self, waypoints = False, radius_change = 0):
        for (edge, next) in self.edges:
                edge.calculate_location()
                if len(edge.waypoints) > 2 and waypoints == True:
    #                print("update edges with waypoints =", waypoints, "; radius change =", radius_change)
                    edge.update_waypoints(edge.waypoints, radius_change, from_outside = False)
        
    # recalculate edges after change in location
    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            # x = value.x()
            # y = value.y()
        #    print("scenepos",self.scenePos(),"itemChange value", value, "x and y", x, y)
        #    print("scenerect",self.scene().sceneRect.x(),self.scene().sceneRect.y())
            self.update_edges()
            self.window.scene.update()

        return super().itemChange(change, value)

class Edge(QGraphicsItem):
    def __init__(self, start: Vertex, end: Vertex, weight, displayed = False, segmented = False, directed = False, curved = True, opacity = 0.5) -> None:
        super().__init__()

        self.__name__ = 'Edge'

        self.displayed = displayed
        self.segmented = segmented
        self.curved = curved
        self.track_drawing = False
        self.opacity = opacity
        
        self.directed = directed
        if main.G.is_directed() == True:
            self.directed = True

        self.start = start
        self.end = end
        self.weight = weight
        
        self.start.addEdge((self, end))
        self.end.addEdge((self, start))

        self.setZValue(-0.5)
        self.setOpacity(self.opacity)

        self.line = QLineF()
        self.color = "black"
        self.thickness = 1
    
        self.waypoints = [self.start.pos() + self.start.boundingRect().center(), self.end.pos() + self.end.boundingRect().center()]
        
        self.calculate_location()

        self.arrow_size = 10

        
        # if self.start.id == "n154" and self.end.id == "n149":
        #     self.track_drawing = True
    
    def update_waypoints(self, waypoints_list, radius_change = 0, from_outside = True):
        self.waypoints = copy.deepcopy(waypoints_list)
        if len(self.waypoints) > 2:
            for count, waypoint in enumerate(self.waypoints):
                if count not in [0, len(self.waypoints)-1]:
                    x_value = waypoint.x()
                    if from_outside:
                        y_value = -waypoint.y() + self.start.window.node_radius
                    else:
                        y_value = waypoint.y() #- radius_change
                    self.waypoints[count] = QPointF(x_value, y_value)

        self.calculate_location(waypoint_update = True)
        self.update()
        
    def toggle_segmentation(self):
        self.segmented = not self.segmented
        self.calculate_location()

    def toggle_curving(self):
        self.curved = not self.curved
        self.calculate_location()

    def calculate_location(self, waypoint_update = False):
        self.prepareGeometryChange()
        if waypoint_update:
            #print("calling calculate location for long")
            starting_point = self.waypoints[0]
            ending_point = self.waypoints[len(self.waypoints)-1]
        else:
            starting_point = self.start.pos() + self.start.boundingRect().center()
            ending_point = self.end.pos() + self.end.boundingRect().center()
            self.waypoints[0] = starting_point
            self.waypoints[len(self.waypoints)-1] = ending_point
        
        self.line = QLineF(
            self.start.pos() + self.start.boundingRect().center(),
            self.end.pos() + self.end.boundingRect().center(),
        )
        if self.segmented == False:
            self.lines = [self.line]
        else:
            self.lines = []
            for count in range(len(self.waypoints)-1):
                line = QLineF(
                    self.waypoints[count],
                    self.waypoints[count+1]
                )
                self.lines.append(line)

        self.buildPath()

        if len(self.waypoints)> 2 and self.track_drawing:
            # print("for line between nodes",self.start.id,"and",self.end.id)
            # print("self waypoints is:", self.waypoints)
            # print ("self lines is:",self.lines)
            pass
        
    # function for building bezier curves, adapted from https://stackoverflow.com/questions/63016214/drawing-multi-point-curve-with-pyqt5   as there's no geometric library for bezier curves in QT
    def buildPath(self):
        factor = 0.25
        waypoints_list = copy.deepcopy(self.waypoints)
        self.path = QPainterPath(waypoints_list[0])
        if len(waypoints_list) == 2:
            self.path.quadTo(waypoints_list[0], waypoints_list[-1])
        else:
            for p, current in enumerate(waypoints_list):
                if p == 0:
                    continue
                elif p == len(waypoints_list) - 1 :
                    break
                # previous segment
                source = QLineF(waypoints_list[p - 1], current)
                # next segment
                target = QLineF(current, waypoints_list[p + 1])
                targetAngle = target.angleTo(source)
                if targetAngle > 180:
                    angle = (source.angle() + source.angleTo(target) / 2) % 360
                else:
                    angle = (target.angle() + target.angleTo(source) / 2) % 360

                revTarget = QLineF.fromPolar(source.length() * factor, angle + 180).translated(current)
                cp2 = revTarget.p2()

                if p == 1:
                    self.path.quadTo(cp2, current)
                else:
                    # use the control point "cp1" set in the *previous* cycle
                    self.path.cubicTo(cp1, cp2, current)

                revSource = QLineF.fromPolar(target.length() * factor, angle).translated(current)
                cp1 = revSource.p2()

            # the final curve, that joins to the last point
            self.path.quadTo(cp1, waypoints_list[-1])
    
    def boundingRect(self) -> QRectF:
        if self.segmented == False:
            return (
                QRectF(self.line.p1(), self.line.p2())
                .normalized()
            )
        else:
            min_y = 9999
            max_y = -9999
            min_x = 9999
            max_x = -9999
            for line in self.lines:
                min_y = min(line.p1().y(), min_y)
                min_x = min(line.p1().x(), min_x)
                max_y = max(line.p2().y(), max_y)
                max_x = max(line.p2().x(), max_x)
            return (
                QRectF(topleft = QPointF(min_x, min_y), bottomright = QPointF(max_x,max_y))
                .normalized()
            )


    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None):
        if self.start and self.end and self.displayed:
            painter.setRenderHints(QPainter.Antialiasing)

            painter.setPen(
                QPen(
                    QColor(self.color),
                    self.thickness,
                    Qt.SolidLine,
                    Qt.RoundCap,
                    Qt.RoundJoin,
                )
            )
            

            if self.directed and self.segmented and (self.start.window.check_for_layered_layout() or main.subgraphs_included):                    # directed and segmented and layered
                if self.curved == True:
                    # if self.track_drawing:
                    #     print("directed, segmented, curved")
                    painter.drawPath(self.path)
                    start = self.waypoints[len(self.waypoints)-2]
                    end = self.waypoints[len(self.waypoints)-1]
                    self.draw_arrow(painter, start, self.arrow_target(start,end), just_head = True)
                else:
                    # if self.track_drawing:
                    #     print("directed, segmented, no curves")
                    for line in self.lines:
                        if line == self.lines[len(self.lines)-1]:
                            start = self.waypoints[len(self.waypoints)-2]
                            end = self.waypoints[len(self.waypoints)-1]
                            self.draw_arrow(painter, start, self.arrow_target(start,end))
                        else:
                            painter.drawLine(line)                    
            elif self.segmented and (self.start.window.check_for_layered_layout() or main.subgraphs_included):                                    # not directed and segmented and layered
                if self.curved == True:
                    painter.drawPath(self.path)
                else:
                    for line in self.lines:
                        painter.drawLine(line)
            elif self.directed:                                     # directed and not segmented
                start = self.line.p1()
                end = self.line.p2()
                self.draw_arrow(painter, start, self.arrow_target(start,end))
            else:                                                   # neither directed nor segmented
                painter.drawLine(self.line) 

                

# function adapted from the QT for Python documentation examples
    def draw_arrow(self, painter: QPainter, start: QPointF, end: QPointF, just_head = False):
        painter.setBrush(QBrush(self.color))

        line = QLineF(end, start)

        angle = np.arctan2(-line.dy(), line.dx())
        arrow_p1 = line.p1() + QPointF(
            np.sin(angle + np.pi / 3) * self.arrow_size,
            np.cos(angle + np.pi / 3) * self.arrow_size,
        )
        arrow_p2 = line.p1() + QPointF(
            np.sin(angle + np.pi - np.pi / 3) * self.arrow_size,
            np.cos(angle + np.pi - np.pi / 3) * self.arrow_size,
        )

        arrow_head = QPolygonF()
        arrow_head.clear()
        arrow_head.append(line.p1())
        arrow_head.append(arrow_p1)
        arrow_head.append(arrow_p2)
        if not just_head:
            painter.drawLine(line)
        painter.drawPolygon(arrow_head)

# function adapted from the QT for Python documentation examples        
    def arrow_target(self, target, center) -> QPointF:
        #target = self.line.p1()
        #center = self.line.p2()
        radius = self.end.radius
        vector = target - center
        length = np.sqrt(vector.x() ** 2 + vector.y() ** 2)
        if length == 0:
            return target
        normal = vector / length
        target = QPointF(center.x() + (normal.x() * radius), center.y() + (normal.y() * radius))

        return target

class VertexBoxes(QGraphicsItem):
    def __init__(self, window):
        super().__init__()
        self.path_list = []
        self.boxes = []
        self.outlines = []
        self.window = window
        self.__name__ = "vertexbox object"

        # outline settings
        self.thickness = 2
        self.color = "brown"
        

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget=None):
        painter.setRenderHints(QPainter.Antialiasing)

        pen_fifteen = QPen(
                QColor(self.color),
                self.thickness,
                Qt.SolidLine,
                Qt.RoundCap,
                Qt.RoundJoin,
            )

        painter.setPen(pen_fifteen)


        painter.setBrush(QBrush(QColor(self.color)))
        self.update_path()

        old_man = QPainterPathStroker(pen_fifteen)

        for box in self.boxes:
            outline = old_man.createStroke(box)
            painter.drawPath(outline)

        
    def update_path(self):
        self.boxes = []
        self.outlines = []
        self.path_list = []
        self.big_path = QPainterPath()
        
        for index in range(len(self.window.vertices)):
            path = QPainterPath()
            for vertex_object in self.window.vertices[index].values():
                path.addRect(vertex_object.physical_location())
            self.path_list.append(path)
            self.big_path.addPath(path)
            
        for path in self.path_list:
            box = path.controlPointRect()
            box_path = QPainterPath() 
            box_path.addRect(box)
            self.boxes.append(box_path)

        
    def boundingRect(self):
        self.update_path()
        return self.big_path.controlPointRect()



class MainWindow(QMainWindow):
    def __init__(self, given_adjacency_dict_list, initial_layout = "random", default_radius = 10) -> None:
        super().__init__()
        self.setWindowTitle("Graph viewer app")

         # Menu
        self.menu = self.menuBar()
        self.file_menu = self.menu.addMenu("File")
        self.layouts_menu = self.menu.addMenu("Layout")
        self.actions_menu = self.menu.addMenu("Actions")
        

        # Exit QAction
        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)

        self.file_menu.addAction(exit_action)

        # manual movement
        movability_action = QAction("Toggle Manual Movement", self)
        movability_action.triggered.connect(self.vertices_toggle_movability)
        movability_action.setCheckable(True)
        movability_action.setChecked(True)
        self.actions_menu.addAction(movability_action)

        id_visibility_action = QAction("Toggle Node ID Visibility", self)
        id_visibility_action.triggered.connect(self.vertices_toggle_id_visibility)
        id_visibility_action.setCheckable(True)
        id_visibility_action.setChecked(True)
        self.actions_menu.addAction(id_visibility_action)

        non_tree_edge_display_action = QAction("Show Non-Tree Edges", self)
        non_tree_edge_display_action.triggered.connect(self.toggle_nontree_edge_display)
        non_tree_edge_display_action.setCheckable(True)
        non_tree_edge_display_action.setChecked(False)
        self.actions_menu.addAction(non_tree_edge_display_action)

        segmentation_toggle_action = QAction("Toggle Edge Segmentation", self)
        segmentation_toggle_action.triggered.connect(self.toggle_edge_segmentation)
        segmentation_toggle_action.setCheckable(True)
        if main.G.is_directed() or main.subgraphs_included:
            segmentation_toggle_action.setChecked(True)
        self.actions_menu.addAction(segmentation_toggle_action)

        curved_segmentation_toggle_action = QAction("Toggle Edge Curving for Segmented Layout", self)
        curved_segmentation_toggle_action.triggered.connect(self.toggle_edge_curving)
        curved_segmentation_toggle_action.setCheckable(True)
        curved_segmentation_toggle_action.setChecked(True)
        self.actions_menu.addAction(curved_segmentation_toggle_action)

        opacity_decrease_action = QAction("Increase Edge Transparency", self)
        opacity_decrease_action.triggered.connect(self.edges_decrease_opacity)
        self.actions_menu.addAction(opacity_decrease_action)

        opacity_increase_action = QAction("Decrease Edge Transparency", self)
        opacity_increase_action.triggered.connect(self.edges_increase_opacity)
        self.actions_menu.addAction(opacity_increase_action)

        radius_increase_action = QAction("Increase Node Size",self)
        radius_increase_action.triggered.connect(self.vertices_increase_radius)
        self.actions_menu.addAction(radius_increase_action)

        radius_decrease_action = QAction("Decrease Node Size",self)
        radius_decrease_action.triggered.connect(self.vertices_decrease_radius)
        self.actions_menu.addAction(radius_decrease_action)

        arrow_increase_action = QAction("Increase Arrow Size", self)
        arrow_increase_action.triggered.connect(self.arrow_increase_size)

        arrow_decrease_action = QAction("Decrease Arrow Size", self)
        arrow_decrease_action.triggered.connect(self.arrow_decrease_size)

        if main.G.is_directed() == True:
            self.actions_menu.addAction(arrow_increase_action)
            self.actions_menu.addAction(arrow_decrease_action)

        dynamic_force_layout_action = QAction("Enable Dynamic Forces on Force-Directed Layout",self)
        dynamic_force_layout_action.triggered.connect(self.toggle_dynamic_forces)
        self.actions_menu.addAction(dynamic_force_layout_action)
        dynamic_force_layout_action.setCheckable(True)
        dynamic_force_layout_action.setChecked(False)

        force_custom_regeneration_action = QAction("Apply Force Direction on Current Layout", self)
        force_custom_regeneration_action.setShortcut(Qt.Key_F)
        force_custom_regeneration_action.triggered.connect(self.regenerate_force_custom)
        self.actions_menu.addAction(force_custom_regeneration_action)

            # graph regeneration
        layout_regeneration_action = QAction("Regenerate Layout", self) # will regenerate with same layout
        layout_regeneration_action.triggered.connect(self.regenerate)
        layout_regeneration_action.setShortcut(QKeySequence.Refresh)
        self.layouts_menu.addAction(layout_regeneration_action)

        random_regeneration_action = QAction("Generate Random Layout", self) # will regenerate with random layout
        random_regeneration_action.triggered.connect(self.regenerate_random)
        self.layouts_menu.addAction(random_regeneration_action)

        solar_regeneration_action = QAction("Generate Random Solar Layout", self) # will regenerate with solar layout, random angles
        solar_regeneration_action.triggered.connect(self.regenerate_solar)
        self.layouts_menu.addAction(solar_regeneration_action)

        deterministic_solar_regeneration_action = QAction("Generate Deterministic Solar Layout", self) # will regenerate with solar layout, consistent angles
        deterministic_solar_regeneration_action.triggered.connect(self.regenerate_solar_deterministic)
        self.layouts_menu.addAction(deterministic_solar_regeneration_action)

        radial_bfs_regeneration_action = QAction("Generate Radial BFS Tree Layout", self)
        radial_bfs_regeneration_action.triggered.connect(self.regenerate_radial_bfs)
        if main.subgraphs_included == False:
            self.layouts_menu.addAction(radial_bfs_regeneration_action)

        radial_dfs_regeneration_action = QAction("Generate Radial DFS Tree Layout", self)
        radial_dfs_regeneration_action.triggered.connect(self.regenerate_radial_dfs)
        if main.subgraphs_included == False:
            self.layouts_menu.addAction(radial_dfs_regeneration_action)

        radial_prims_regeneration_action = QAction("Generate Radial Prim's Tree Layout", self)
        radial_prims_regeneration_action.triggered.connect(self.regenerate_radial_prims)
        if main.subgraphs_included == False:
            self.layouts_menu.addAction(radial_prims_regeneration_action)

        force_random_regeneration_action = QAction("Generate Force Directed Random-Initialized Layout", self)
        force_random_regeneration_action.triggered.connect(self.regenerate_force_random)
        self.layouts_menu.addAction(force_random_regeneration_action)

        force_bfs_regeneration_action = QAction("Generate Force Directed BFS-Initialized Layout", self)
        force_bfs_regeneration_action.triggered.connect(self.regenerate_force_bfs)
        if main.subgraphs_included == False:
            self.layouts_menu.addAction(force_bfs_regeneration_action)         # do not include this with subgraphs until bfs is exhaustive

        dag_dfs_barycenter_regeneration_action = QAction("Generate DAG DFS-Initialized Layout (Barycenter crossing minimization)", self)
        dag_dfs_barycenter_regeneration_action.triggered.connect(self.regenerate_dag_dfs_barycenter)
        if main.subgraphs_included == False:
            self.layouts_menu.addAction(dag_dfs_barycenter_regeneration_action)

        dag_dfs_median_regeneration_action = QAction("Generate DAG DFS-Initialized Layout (Median crossing minimization)", self)
        dag_dfs_median_regeneration_action.triggered.connect(self.regenerate_dag_dfs_median)
        if main.subgraphs_included == False:
            self.layouts_menu.addAction(dag_dfs_median_regeneration_action)

         # Status Bar
        self.status = self.statusBar()
        self.status.showMessage("Graph loaded and displayed - layout: "+initial_layout)

        # Window dimensions
        geometry = self.screen().availableSize()
        self.screenwidth = geometry.width() * 0.7
        self.screenheight = geometry.height() * 0.7
        self.setFixedSize(self.screenwidth, self.screenheight)
        
        # random coordinates for now
        self.default_layout = initial_layout
        self.default_radius = default_radius
        self.node_radius = default_radius
        
        # Scene and view
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)

        #self.scene.setSceneRect(-self.screenwidth/2 + 25, -self.screenheight/2 + 50, self.screenwidth - 50, self.screenheight - 75)

        
        self.vertices = []
        self.inter_layer_adjacency_dict = None
        self.interlayer_edge_objects = []
        self.vertex_boxes = VertexBoxes(window = self)
        
        if len(given_adjacency_dict_list) > 1:
            self.adjacency_dict = []
            for count in range(len(given_adjacency_dict_list)):
                if count == len(given_adjacency_dict_list) - 1:
                    self.inter_layer_adjacency_dict = given_adjacency_dict_list[count]
                else:
                    self.adjacency_dict.append(given_adjacency_dict_list[count])
                    self.vertices.append({})
            self.vertex_boxes.update_path()
            self.scene.addItem(self.vertex_boxes)

        else:
            self.adjacency_dict = given_adjacency_dict_list
            self.vertices.append({})

        # Coordinates
        self.dfs_list = []
        self.bfs_list = []
        self.prims_list = []
        self.all_vertices = {}
        self.all_edges = {}
        self.tree = None
        self.treetype = None
        self.coordinates = []
        
        for count in range(len(self.vertices)):
            self.initialize_vertices(index = count)

        if self.inter_layer_adjacency_dict != None:
            #print("initializing interlayer edges based on dict", self.inter_layer_adjacency_dict)
            self.initialize_interlayer_edges()

        # Subgraph settings
        self.default_subgraph_distance = (self.screenwidth - 50 - self.node_radius * 2)  / 2        
        self.show_subgraph_boxes = True  

        # Default Settings
        self.layout = self.default_layout
        self.first_generation = True
        self.display_non_tree_edges = False
        self.dynamic_forces = False
        self.strict_force_binding = True
        self.edge_bundling_bool = True                   # todo: add layout option for toggling this is subgraphs are included
        self.regenerate()

        assert (self.visibility(p_start = (0,0) ,p_end = (0,10), q_start = (10,0), q_end = (10,10), printing = False) == 1.0)
        # print("testvis is",test_vis)      # should be 1
        assert (self.visibility(p_start = (0,0) ,p_end = (1,0), q_start = (0.5,1), q_end = (1.5,1.0), printing = False) == 0)
        
        assert(self.visibility(p_start = (0,0) ,p_end = (10,0), q_start = (5,10), q_end = (15,10), printing = False) == 0)
        
 
        self.view.show()

        if main.printing_mode:
            print("window width and height:", self.screenwidth, self.screenheight)
            print("scene width:", self.scene.width(), "scene height:", self.scene.height())
            print("view width:", self.view.width(), "view height:", self.view.height())
        
        #self.depth_first_search_exhaustive()
            
        # graphics displayed in the center
        self.setCentralWidget(self.view)

    
    def update_status(self):
        self.status.showMessage("Graph loaded and displayed - layout: "+self.layout)

    def update_node_position(self, node_id, x, y, index = 0):
        self.coordinates[index][node_id] = (x,y)

    def check_for_tree_layout(self):
        if self.layout == "force custom":
            return self.tree
        elif self.layout in ["radial dfs","radial bfs", "radial prims"]:
            self.tree = True
            return True
        else:
            self.tree = False
            return False

    def check_for_layered_layout(self):
        if self.layout in ["dag dfs barycenter", "dag dfs median"]:
            return True
        else:
            return False
        
    def translate_coordinates(self, coordinates, xtrans = 0, ytrans = 0):
        """
        get a x and y translation as input, and a coordinates dictionary with node ids as key and a tuple as coordinates as a value
        """
        translated_coordinates = coordinates.copy()

        for node_id, val in coordinates.items():
            new_x = val[0] + xtrans
            new_y = val[1] + ytrans
            translated_coordinates[node_id] = (new_x, new_y)

        return translated_coordinates    
        
        
 # layout selector             
    def generate(self, layout, subgraph_distance = None, use_screen_attributes = True, width = None, height = None, index = 0, random_subgraph_shuffle = False):
        if use_screen_attributes:
            width = self.screenwidth - 50 - self.node_radius * 2
            height = self.screenheight - 75 - self.node_radius * 2
        else:
            if width == None or height == None:
                raise ValueError ("Need to input custom width or height values for the box")

        if len(self.coordinates) < (index+1):
            self.coordinates.append([])

                
        self.layout = layout
        if self.layout == "random":
            if main.subgraphs_included and not random_subgraph_shuffle:
                self.coordinates[index] = main.create_random_coordinates(width/2, height, self.adjacency_dict[index])
            else:
                self.coordinates[index] = main.create_random_coordinates(width, height, self.adjacency_dict[index])
        elif self.layout == ("solar" or "solar random"):
            self.coordinates[index] = main.create_solar_coordinates(width, height, self.adjacency_dict[index], index = index)
        elif self.layout == "solar deterministic":
            self.coordinates[index] = main.create_solar_coordinates(width, height, self.adjacency_dict[index], index = index, deterministic = True)
        elif self.layout == "radial dfs":
            if self.dfs_list == []:
                for count in range(len(self.vertices)):
                    self.depth_first_search(root=main.most_connected_node_id[count], index = count)
            self.treetype = "dfs"                
            self.coordinates[index] = main.create_radial_coordinates(width, height, self.dfs_list[index], self.node_radius)
        elif self.layout == "radial bfs":
            if self.bfs_list == []:
                for count in range(len(self.vertices)):
                    self.breadth_first_search(root=main.most_connected_node_id[count], index = count)
                    
            self.treetype = "bfs"
            self.coordinates[index] = main.create_radial_coordinates(width, height, self.bfs_list[index], self.node_radius)
        elif self.layout == "radial prims":
            if self.prims_list == []:
                for count in range(len(self.vertices)):
                    self.prims_algorithm(root=main.most_connected_node_id[count], index = count)
            self.treetype = "prims"
            self.coordinates[index] = main.create_radial_coordinates(width, height, self.prims_list[index], self.node_radius)
            
        elif self.layout == "force bfs":            # do not use this until bfs has been made exhaustive
            if self.bfs_list == []:
                for count in range(len(self.vertices)):
                    self.breadth_first_search(root=main.most_connected_node_id[count], index = count)
            bfs_coords = main.create_radial_coordinates(width, height, self.bfs_list[index], self.node_radius)
            print("calculating force bfs coordinates for index",index)
            self.coordinates[index] = main.create_force_layout_coordinates(width, height, bfs_coords, self.adjacency_dict[index], index = index)

        elif self.layout == "force random":
            
            if main.subgraphs_included:
                random_coords = main.create_random_coordinates(width/2, height, self.adjacency_dict[index])
                self.coordinates[index] = main.create_force_layout_coordinates(width/2, height, random_coords, self.adjacency_dict[index], max_iterations = 150, index = index)
                if index == 0:
                    self.coordinates[index] = self.translate_coordinates(self.coordinates[index], -subgraph_distance/2, 0)
                else:
                    self.coordinates[index] = self.translate_coordinates(self.coordinates[index], subgraph_distance/2, 0)

                self.coordinates[index] = main.create_force_layout_coordinates(width, height, self.coordinates[index], self.adjacency_dict[index], max_iterations = 50, index = index)       # extra iterations

            else:
                random_coords = main.create_random_coordinates(width, height, self.adjacency_dict[index])
                self.coordinates[index] = main.create_force_layout_coordinates(width, height, random_coords, self.adjacency_dict[index], index = index)

            
        elif self.layout == "force custom":
            if self.strict_force_binding == True:
                self.coordinates[index] = main.create_force_layout_coordinates(width, height, self.coordinates[index], self.adjacency_dict[index], max_iterations=50, index = index)
            else:
                self.coordinates[index] = main.create_force_layout_coordinates(self.scene.width(), self.scene.height(), self.coordinates[index], self.adjacency_dict[index], max_iterations=50, index = index)

        elif self.layout == "dag dfs barycenter":
            if self.dfs_list == []:
                for count in range(len(self.vertices)):
                    self.depth_first_search(root=main.most_connected_node_id[count], index = count)
            self.coordinates[index], edge_waypoints = main.calc_DAG(width, height, self.dfs_list[index], self.adjacency_dict[index], minimization_method="barycenter")
            self.update_edge_waypoints(edge_waypoints)
            
        elif self.layout == "dag dfs median":
            if self.dfs_list == []:
                for count in range(len(self.vertices)):
                    self.depth_first_search(root=main.most_connected_node_id[count], index = count)
            self.coordinates[index], edge_waypoints = main.calc_DAG(width, height, self.dfs_list[index], self.adjacency_dict[index], minimization_method="median")
            self.update_edge_waypoints(edge_waypoints)
        else:
            print("asked for layout", layout)
            raise ValueError ("Unsupported layout "+layout+" requested")
        
#        print("the resulting coordinates on index",index, "are for node",self.coordinates[index].keys())

    def update_edge_waypoints(self, edge_waypoints):    # key: list of edges where edge is (start_node_id, end_node_id, weight); value: [coords of start, dummy, ..., end]
  #      print("self.all_edges.keys():", self.all_edges.keys())

  #     print("waypoint items are:",edge_waypoints)

        for edge_triple, waypoints_list in edge_waypoints.items():
   #         print("edge triple is",edge_triple,"; waypoints list is",waypoints_list)
            edge_object = self.all_edges[edge_triple]       # key: (start_node_id, end_node_id, weight); value: edge object
            edge_object.update_waypoints(waypoints_list)

            print("edge from",edge_object.start.id,"to",edge_object.end.id,"gets waypoint coordinates of",waypoints_list)
    #    print("edge waypoint updating complete")
            
        self.scene.update()


# recreate the graph
    def regenerate(self, same_positions = False, subgraph_distance = None):
        if main.printing_mode:
            print("calling regenerate")
            print("asking for layout", self.layout)

        if subgraph_distance == None:
            subgraph_distance = self.default_subgraph_distance
            
        # create new set of coordinates based on the current layout
        if not same_positions:
            for index in range(len(self.vertices)):
                self.generate(self.layout, index = index, subgraph_distance = subgraph_distance)
        
        if (self.first_generation == False and self.check_for_tree_layout() == True):
            for item in self.scene.items():
                item.displayed = False

        if len(self.vertices) > 1 and self.layout not in ["force custom", "force random"]:
            for index, untranslated_coordinates in enumerate(self.coordinates):
                if index == 0:
                    self.coordinates[index] = self.translate_coordinates(untranslated_coordinates, -subgraph_distance/2, 0)
                else:
                    self.coordinates[index] = self.translate_coordinates(untranslated_coordinates, subgraph_distance/2, 0)



        # move the vertices to their new positions
     #   print("self coordinates index 0 keys:",self.coordinates[0].keys())
      #  print("self coordinates index 1 keys", self.coordinates[1].keys())

        for index in range(len(self.coordinates)):
            #print("moving all vertices of index",index)
            #print("these are:",self.coordinates[index].keys())
            for vertex_id in self.coordinates[index].keys():
                x,y = self.coordinates[index][vertex_id]

                if main.printing_mode:
                    print("reset vertex",vertex_id,"at x_val",x,"and y_val",-y)

                self.all_vertices[vertex_id].moveVertex(x,-y)
                
                if self.check_for_tree_layout() and not self.display_non_tree_edges:
                    self.all_vertices[vertex_id].turnVisible(edge_update = False)
                else:
                    self.all_vertices[vertex_id].turnVisible()
                
    # get self.dfs, for parent in selfdfs element [0], check all the edges for next to be element [1], turn on that edge only; make sure update function doesn't update other edges
        if self.check_for_tree_layout() and not self.display_non_tree_edges:
            if self.treetype == "dfs":
                tree = self.dfs_list
            elif self.treetype == "bfs":
                tree = self.bfs_list
            elif self.treetype == "prims":
                tree = self.prims_list
            else:
                raise ValueError ("No selected node list in given tree layout")

            for node_list in tree:
                for parent_id, child_id in node_list:
            #        print("testing to see if tree displays edge", parent_id,"to",child_id)
                    for edge, next in self.all_vertices[parent_id].edges:
            #            print("node",parent_id,"has edge to:",next.id)
                        if next == self.all_vertices[child_id]:
                            edge.displayed = True
                            # edge.color = "blue"               # highlighting tree edges
                            # edge.setZValue(-0.3)
                            edge.update()
            #                print("tree displaying edge",parent_id, "to", child_id)

        self.update_status()               


        if self.edge_bundling_bool and main.subgraphs_included:
            print("starting edge bundling")
            self.edge_bundling()
        
        
        new_bounding_rect = self.scene.itemsBoundingRect()
        self.scene.setSceneRect(new_bounding_rect)
        self.scene.update()
        self.view.updateSceneRect(new_bounding_rect)
        self.first_generation = False

        if main.printing_mode:
            print("window width and height:", self.screenwidth, self.screenheight)
            print("scene width:", self.scene.width(), "scene height:", self.scene.height())
            print("view width:", self.view.width(), "view height:", self.view.height())
        
    def edge_bundling(self, max_loops = 6, edge_objects = None, k=0.1, s_0 = 0.04, compat_threshold = 0.05):
        if edge_objects == None:
            edge_objects = self.interlayer_edge_objects     #self.interlayer_edge_objects is the list af all edge objects that need to be bundled    
            
        for edge in edge_objects:           # reset waypoints in case the layout is regenerated
            start = edge.waypoints[0]
            end = edge.waypoints[-1]
            edge.waypoints = [start,end]

        # for edge in edge_objects:
        #         print("edge from",edge.start.id,"to",edge.end.id,"has waypoints", edge.waypoints)
        # for edge in edge_objects:
        #     if edge.start.id == "n154" and edge.end.id == "n149":
        #         print("before cycles, edge from",edge.start.id,"to",edge.end.id,"has waypoints", edge.waypoints, "and lines",edge.lines)    
            
        for cycle in range(max_loops):
            print("starting cycle",cycle)
            self.subdivide_all_edges(edge_objects)
            # for edge in edge_objects:
            #     if edge.start.id == "n154" and edge.end.id == "n149":
            #         print("after subdivision, edge from",edge.start.id,"to",edge.end.id,"has waypoints", edge.waypoints, "and lines",edge.lines) 
            self.perform_edge_bundling(edge_objects, cycle, s_0, compat_threshold)
            # for edge in edge_objects:
            #     if edge.start.id == "n154" and edge.end.id == "n149":
            #         print("after edge bundling, edge from",edge.start.id,"to",edge.end.id,"has waypoints", edge.waypoints, "and lines",edge.lines) 
  
        
        # for edge in edge_objects:
        #     print("after cycle", max_loops - 1,", edge from",edge.start.id,"to",edge.end.id,"has waypoints", edge.waypoints)

        for edge in edge_objects:
            edge.calculate_location(waypoint_update = True)

        # for edge in edge_objects:
        #     if edge.start.id == "n154" and edge.end.id == "n149":
        #         print("after calculate location, edge from",edge.start.id,"to",edge.end.id,"has waypoints", edge.waypoints, "and lines",edge.lines)    
        
        self.scene.update()

    def subdivide_edge(self, edge):
     #   n = 2 * (cycle - 1)
        old_waypoints = copy.deepcopy(edge.waypoints)

        count = 0
        for index, waypoint in enumerate(old_waypoints):
            if index != len(old_waypoints) - 1:
                
                x1 = waypoint.x()
                y1 = waypoint.y()
                x2 = old_waypoints[index + 1].x()
                y2 = old_waypoints[index + 1].y()

                x_new = (x1 + x2) / 2
                y_new = (y1 + y2) / 2

                edge.waypoints.insert(index + 1 + count, QPointF(x_new, y_new))
                count += 1

        # print("waypoints of edge from",edge.start.id,"to",edge.end.id, "after subdivision are", edge.waypoints)


    def subdivide_all_edges(self, edge_objects):
        for edge in edge_objects:
            self.subdivide_edge(edge)

    def perform_edge_bundling(self, edge_objects, cycle, s_0, compat_threshold):

        s = s_0 / (2**(cycle))          # this is the delta value

        x_modifications = {}
        y_modifications = {}
        for i in range(len(edge_objects)):
            x_modifications[edge_objects[i]] = np.zeros(len(edge_objects[i].waypoints))
            y_modifications[edge_objects[i]] = np.zeros(len(edge_objects[i].waypoints))            

        for i in range(len(edge_objects)):
            for j in range(i+1, len(edge_objects)):
                #if edge_objects[i].interlayer() != edge_objects[j].interlayer:
                #    continue

                # calculate edge vectors from the edge object in (x,y) tuples
                compat = self.main_compat(edge_objects[i], edge_objects[j])
#                print("compat value is",compat,"while the treshold is",compat_threshold)

                if compat > compat_threshold:
                    force1, force2 = self.force_calculation(edge_objects[i], edge_objects[j], compat, 1)
                    # print("force1, force2", force1, force2)

                    for k in range(1, len(edge_objects[i].waypoints) - 1):
                        waypoint_i = edge_objects[i].waypoints[k]
                        waypoint_j = edge_objects[j].waypoints[k]

                        vector_i = (waypoint_j.x() - waypoint_i.x(), waypoint_j.y() - waypoint_i.y())
                        vector_j = (-vector_i[0], -vector_i[1])

                        dx_i  = vector_i[0] * force1[k]         # magnitude * direction
                        dy_i  = vector_i[1] * force1[k]

                        dx_j = vector_j[0] * force2[k]
                        dy_j = vector_j[1] * force2[k]

                        # print("dx_i", dx_i)
                        # print("dy_i", dy_i)
                        # print("dx_j", dx_j)
                        # print("dy_j", dy_j)
                        

                        x_modifications[edge_objects[i]][k] += dx_i * s
                        y_modifications[edge_objects[i]][k] += dy_i * s

                        x_modifications[edge_objects[j]][k] += dx_j * s
                        y_modifications[edge_objects[j]][k] += dy_j * s

        for i in range(len(edge_objects)):
            for k in range(1, len(edge_objects[i].waypoints) - 1):
                e = edge_objects[i]
                e.waypoints[k] = QPointF(e.waypoints[k].x() + x_modifications[e][k], e.waypoints[k].y() + y_modifications[e][k])
                    

    # def bundle_edges(self, e1, e2, compat_value, scale):
    #     force_values_e1 = []
    #     force_values_e2 = []
    #     for i in range(len(e1[0].waypoints)):
    #         if i == 0 or i == len(e1[0].waypoints) - 1:
    #             force_values_e1.append((0, 0))
    #             force_values_e2.append((0, 0))
    #             continue
    #         f_e1, f_e2 = self.force_calculation(e1[0].waypoints[i], e2[0].waypoints[i], compat_value, scale)
    #         force_values_e1.append(f_e1)
    #         force_values_e2.append(f_e2)
    #     return force_values_e1, force_values_e2

    def main_compat(self, e1, e2):
        # print("angle:", self.angle_compat(e1, e2), "scale:", self.scale_compat(e1, e2), "distance:", self.distance_compat(e1, e2), "visibility:", self.visibility_compat(e1, e2))
        # print("total compat without scale:",  self.angle_compat(e1, e2) * self.distance_compat(e1, e2) * self.visibility_compat(e1, e2)  )
        return self.angle_compat(e1, e2) * self.distance_compat(e1, e2)  * self.visibility_compat(e1, e2)  # * self.scale_compat(e1, e2)

    def angle_compat(self, e1, e2):
        #print("e1", e1)
        e1_vec = (e1.end.x_coord - e1.start.x_coord, e1.end.y_coord - e1.start.y_coord) 
        e2_vec = (e2.end.x_coord - e2.start.x_coord, e2.end.y_coord - e2.start.y_coord) 
        p_times_q_dot = e1_vec[0] * e2_vec[0] + e1_vec[1] * e2_vec[1]
        p_length = math.sqrt(e1_vec[0] * e1_vec[0] + e1_vec[1] * e1_vec[1])
        q_length = math.sqrt(e2_vec[0] * e2_vec[0] + e2_vec[1] * e2_vec[1])
        dot_pq =  p_times_q_dot / (p_length * q_length)
        angle_compatibility = abs(dot_pq)
        #print("angle compatability between edges", e1, "and", e2_vec, "is", angle_compatibility)
        return angle_compatibility

    def scale_compat(self, e1, e2):
        e1_vec = (e1.end.x_coord - e1.start.x_coord, e1.end.y_coord - e1.start.y_coord) 
        e2_vec = (e2.end.x_coord - e2.start.x_coord, e2.end.y_coord - e2.start.y_coord) 
        p_length = math.sqrt(e1_vec[0] * e1_vec[0] + e1_vec[1] * e1_vec[1])
        q_length = math.sqrt(e2_vec[0] * e2_vec[0] + e2_vec[1] * e2_vec[1])
        l_avg = (p_length + q_length)/2
        min_length = min(p_length, q_length)
        max_length = max(p_length, q_length)
        scale_compatibility = 2 / ((l_avg * min_length) + (max_length / l_avg))
        #print("scale compatability between edges", e1_vec, "and", e2_vec, "is", scale_compatibility)
        return scale_compatibility

    def distance_compat(self, e1, e2):
        e1_vec = (e1.end.x_coord - e1.start.x_coord, e1.end.y_coord - e1.start.y_coord) 
        e2_vec = (e2.end.x_coord - e2.start.x_coord, e2.end.y_coord - e2.start.y_coord) 
        p_length = math.sqrt(e1_vec[0] * e1_vec[0] + e1_vec[1] * e1_vec[1])
        q_length = math.sqrt(e2_vec[0] * e2_vec[0] + e2_vec[1] * e2_vec[1])
        l_avg = (p_length + q_length)/2
        p_midpoint = ((e1.start.x_coord + e1.end.x_coord) / 2, (e1.start.y_coord + e1.end.y_coord) / 2) 
        q_midpoint = ((e2.start.x_coord + e2.end.x_coord) / 2, (e2.start.y_coord + e2.end.y_coord) / 2) 
        dist_pm_qm = math.sqrt((p_midpoint[0] - q_midpoint[0]) * (p_midpoint[0] - q_midpoint[0]) + 
                               (p_midpoint[1] - q_midpoint[1]) * (p_midpoint[1] - q_midpoint[1]))
        distance_compatibility = l_avg / (l_avg + dist_pm_qm)
        #print("distance compatability between edges", e1_vec, "and", e2_vec, "is", distance_compatibility)
        return distance_compatibility

    def visibility_compat(self, e1, e2):

        e1_start = (e1.start.x_coord, e1.start.y_coord)
        e1_end = (e1.end.x_coord, e1.end.y_coord)
        e2_start = (e2.start.x_coord, e2.start.y_coord)
        e2_end = (e2.end.x_coord, e2.end.y_coord)
        vis_pq = self.visibility(e1_start,e1_end, e2_start,e2_end)
        vis_qp = self.visibility(e2_start,e2_end, e1_start,e1_end)
        visibility_compatibility = min(vis_pq, vis_qp)
        
        #print("visibility compatability between edges", e1_start, e1_end "and", e2_start, e2_end, "is", visibility_compatibility)
        # if visibility_compatibility != 0:
        #     print("visibility compatibility between edges is", visibility_compatibility)
        return visibility_compatibility
    
    def visibility(self, p_start,p_end, q_start, q_end, printing = False):
        # project q on p
        p_start = np.array(p_start)
        p_end = np.array(p_end)
        q_start = np.array(q_start)
        q_end = np.array(q_end)
        if printing:
            print("p goes from",p_start,"to",p_end)
            print("q goes from",q_start,"to",q_end)

        start_vec = q_start - p_start
        end_vec = q_end - p_end
        p_vec = p_end - p_start

        i_0 = p_start + np.dot(start_vec, p_vec) / np.dot(p_vec, p_vec) * p_vec
        i_1 = p_end + np.dot(end_vec, p_vec) / np.dot(p_vec, p_vec) * p_vec
        if printing:
            print("i_0:",i_0)
            print("i_1:",i_1)

        I_m = self.find_midpoint(i_0, i_1)
        P_m = self.find_midpoint(p_start, p_end)

        if printing:
            print("I_m:",I_m)
            print("P_m:",P_m)
            print("euclidean distance between Pm and Im is:", main.calc_eucl_dist(P_m[0], P_m[1], I_m[0], I_m[1]))

        vis_pq = max(0, 1 - 2 * (main.calc_eucl_dist(P_m[0], P_m[1], I_m[0], I_m[1]))/ main.calc_eucl_dist(i_0[0], i_0[1], i_1[0], i_1[1]))  
        if printing:
             print("vis calc result is", 1 - 2 * (main.calc_eucl_dist(P_m[0], P_m[1], I_m[0], I_m[1])) / main.calc_eucl_dist(i_0[0], i_0[1], i_1[0], i_1[1])) 
        return vis_pq
        # p_vec = np.array(e1_end[0] - e1_start[0], e1_end[1] - e1_start[1]) 
        # q_vec = np.array(e2_end[0] - e2_start[0], e2_end[1] - e2_start[1]) 

        # # project q on p
        # p_norm = np.sqrt(sum(p_vec**2))
        # i_vec = (np.dot(p_vec, q_vec) / p_norm**2) * p_vec
        
    
    def find_midpoint(self, start, end):
        x1, y1 = start
        x2, y2 = end
        return ((x1 + x2) / 2, (y1 + y2)/2)


    def force_calculation(self, e1, e2, compat_value, scale):
        # TODO: calculate force on each waypoint of the two edges and return position modification of those waypoints
        k_stiff = 0.5 # global stiffness constant, the larger the less likely the edges will bundle
        #initialize force lists
        force_e1 = []
        force_e2 = []
        e1_vec = (e1.end.x_coord - e1.start.x_coord, e1.end.y_coord - e1.start.y_coord) 
        e2_vec = (e2.end.x_coord - e2.start.x_coord, e2.end.y_coord - e2.start.y_coord) 
        e1_length = math.sqrt(e1_vec[0] * e1_vec[0] + e1_vec[1] * e1_vec[1])
        e2_length = math.sqrt(e2_vec[0] * e2_vec[0] + e2_vec[1] * e2_vec[1])
        np_e1 = len(e1.waypoints)
        np_e2 = len(e2.waypoints)
        segment_length_e1 = e1_length / np_e1
        segment_length_e2 = e2_length / np_e2
        kp_e1 = k_stiff / segment_length_e1
        kp_e2 = k_stiff / segment_length_e2

        # print("e1 goes from",e1.start.id,"to",e1.end.id,"and e2 goes from",e2.start.id,"to",e2.end.id)
        # print("waypoints of edge from",e1.start.id,"to",e1.end.id, "after subdivision are", e1.waypoints)
        # print("waypoints of edge from",e2.start.id,"to",e2.end.id, "after subdivision are", e2.waypoints)

        for count, waypoint in enumerate(e1.waypoints):
            if not force_e1:
                force_e1.append(0)
            elif len(force_e1) == len(e1.waypoints) - 1:
                force_e1.append(0)
            else: 
                # print("count",count)
                # print("prev waypoint e1", (e1.waypoints[count-1].x(), e1.waypoints[count-1].y()))
                # print("curr waypoint e1", (waypoint.x(), waypoint.y()))
                # print("next waypoint e1", (e1.waypoints[count+1].x(), e1.waypoints[count+1].y()))

                dist_prev_curr_waypoint_e1 = math.sqrt((e1.waypoints[count-1].x() - waypoint.x()) ** 2
                                                    + (e1.waypoints[count-1].y() - waypoint.y()) **2) 
                dist_curr_next_waypoint_e1 = math.sqrt((waypoint.x() - e1.waypoints[count+1].x()) **2   
                                                       + (waypoint.y() - e1.waypoints[count+1].y()) **2) 
                
                force_electro = 0
                for count, waypoint in enumerate(e1.waypoints):
                    dist_pq = math.sqrt((waypoint.x() - e2.waypoints[count].x()) * (waypoint.x() - e2.waypoints[count].x()) +
                                        (waypoint.y() - e2.waypoints[count].y()) * (waypoint.y() - e2.waypoints[count].y()))
                    if dist_pq != 0:
                        force_electro += compat_value / dist_pq
                # print("force electro e1", force_electro)

                # print("kp e1", kp_e1)
                # print("dist_prev_curr e1", dist_prev_curr_waypoint_e1)
                # print("dist_curr_next e1", dist_curr_next_waypoint_e1)
                force_waypoint = kp_e1 * (dist_prev_curr_waypoint_e1 + dist_curr_next_waypoint_e1) + force_electro
                force_e1.append(force_waypoint)

        for count, waypoint in enumerate(e2.waypoints):
            if not force_e2:
                force_e2.append(0)
            elif len(force_e2) == len(e2.waypoints) - 1:
                force_e2.append(0)
            else: 
                # print("prev waypoint e2", (e2.waypoints[count-1].x(), e2.waypoints[count-1].y()))
                # print("curr waypoint e2", (waypoint.x(), waypoint.y()))
                # print("next waypoint e2", (e2.waypoints[count+1].x(), e2.waypoints[count+1].y()))

                dist_prev_curr_waypoint_e2 = math.sqrt((e2.waypoints[count-1].x() - waypoint.x()) ** 2
                                                    + (e2.waypoints[count-1].y() - waypoint.y()) **2) 
                dist_curr_next_waypoint_e2 = math.sqrt((waypoint.x() - e2.waypoints[count+1].x()) **2   
                                                       + (waypoint.y() - e2.waypoints[count+1].y()) **2) 
                
                force_electro = 0
                for count, waypoint in enumerate(e1.waypoints):
                    dist_pq = math.sqrt((waypoint.x() - e2.waypoints[count].x()) * (waypoint.x() - e2.waypoints[count].x()) +
                                        (waypoint.y() - e2.waypoints[count].y()) * (waypoint.y() - e2.waypoints[count].y()))
                    if dist_pq != 0:
                        force_electro += compat_value / dist_pq
                        
                # print("force electro e2", force_electro)
                # print("kp e2", kp_e2)
                # print("dist_prev_curr e2", dist_prev_curr_waypoint_e2)
                # print("dist_curr_next e2", dist_curr_next_waypoint_e2)

                force_waypoint = kp_e2 * (dist_prev_curr_waypoint_e2 + dist_curr_next_waypoint_e2) + force_electro
                force_e2.append(force_waypoint)

    
        return force_e1, force_e2

        return

    def regenerate_random(self):
        self.layout = "random"
        self.regenerate()

    def regenerate_solar(self):
        self.layout = "solar"
        self.regenerate()

    def regenerate_solar_deterministic(self):
        self.layout = "solar deterministic"
        self.regenerate()

    def regenerate_radial_dfs(self):
        self.layout = "radial dfs"
        self.regenerate()

    def regenerate_radial_bfs(self):
        self.layout = "radial bfs"
        self.regenerate()
        
    def regenerate_radial_prims(self):
        self.layout = "radial prims"
        self.regenerate()
    
    def regenerate_force_random(self):
        self.layout = "force random"
        self.regenerate()
        
    def regenerate_force_bfs(self):
        self.layout = "force bfs"
        self.regenerate()
    
    def regenerate_force_custom(self):
        self.layout = "force custom"
        self.regenerate()

    def regenerate_dag_dfs_barycenter(self):
        self.layout = "dag dfs barycenter"
        self.regenerate()
            
    def regenerate_dag_dfs_median(self):
        self.layout = "dag dfs median"
        self.regenerate()

# part of graph initialization:
        
    def initialize_vertices(self, index = 0):
        for vertex_id in self.adjacency_dict[index].keys():
            new_vertex = Vertex(self, vertex_id, 0, 0, radius = self.node_radius, subgraph = index)
            self.vertices[index][vertex_id] = new_vertex
            self.all_vertices[vertex_id] = new_vertex
            self.scene.addItem(new_vertex)
        self.initialize_edges(index)


    def initialize_edges(self, index = 0):
        for start_id in self.adjacency_dict[index].keys():        
            for e_tuple in self.adjacency_dict[index][start_id]:
                end_id, to_create, weight = e_tuple
                if to_create == True:
                    if main.G.is_directed() == True:
                        new_edge = Edge(self.vertices[index][start_id],self.vertices[index][end_id], weight, segmented = True)
                    else:
                        new_edge = Edge(self.vertices[index][start_id],self.vertices[index][end_id], weight, segmented = False)
                    self.scene.addItem(new_edge)
                    self.all_edges[(start_id, end_id, weight)] = new_edge    
        
                    if main.printing_mode:
                        print ("added edge from", start_id, "to", end_id,"with weight",weight)

    def initialize_interlayer_edges(self):
        for start_id in self.inter_layer_adjacency_dict.keys():
            start_index = self.all_vertices[start_id].subgraph            
            for e_tuple in self.inter_layer_adjacency_dict[start_id]:
                end_id, to_create, weight = e_tuple
                end_index = self.all_vertices[end_id].subgraph
                if to_create == True:
                    if main.G.is_directed() == True:
                        new_edge = Edge(self.vertices[start_index][start_id],self.vertices[end_index][end_id], weight, segmented = True)
                    else:
                        new_edge = Edge(self.vertices[start_index][start_id],self.vertices[end_index][end_id], weight, segmented = False)
                    self.scene.addItem(new_edge)
                    self.all_edges[(start_id, end_id, weight)] = new_edge   
                    self.interlayer_edge_objects.append(new_edge) 
                    if main.printing_mode:
                        print ("added interlayer edge from", start_id, "to", end_id,"with weight",weight)                    

    def edges_increase_opacity(self):
        for e in self.scene.items():
            if e.__name__ == 'Edge':
                e.opacity = min(1, e.opacity + 0.1)
                e.setOpacity(e.opacity)
        self.scene.update()                        
    
    def edges_decrease_opacity(self):
        for e in self.scene.items():
            if e.__name__ == 'Edge':
                e.opacity = max(0, e.opacity - 0.1)
                e.setOpacity(e.opacity)
        self.scene.update()
                        
    def vertices_decrease_radius(self):
        for vertices_list in self.vertices:
            for v in vertices_list.values():
                radius_change = v.radius
                v.radius = max(5, v.radius-5)
                self.node_radius = v.radius
                radius_change = radius_change - v.radius
                v.update_edges(waypoints = True, radius_change = radius_change)        
        self.scene.update()

    def vertices_increase_radius(self):
        for vertices_list in self.vertices:
            for v in vertices_list.values():
                radius_change = v.radius
                v.radius += 5
                self.node_radius = v.radius
                radius_change = radius_change - v.radius
                v.update_edges(waypoints = True, radius_change = radius_change)
        self.scene.update()

    def arrow_increase_size(self):
        for e in self.scene.items():
            if e.__name__ == 'Edge':
                e.arrow_size += 2
        self.scene.update()

    def arrow_decrease_size(self):
        for e in self.scene.items():
            if e.__name__ == 'Edge':
                e.arrow_size = max(0, e.arrow_size - 2)
        self.scene.update()
                    
    def vertices_toggle_movability(self):
        for v in self.scene.items():
            if v.__name__ == 'Vertex':
                v.toggle_movability()

    def vertices_toggle_id_visibility(self):
        for v in self.scene.items():
            if v.__name__ == 'Vertex':
                v.toggle_id_visibility()
        self.scene.update()

    def toggle_dynamic_forces(self):
        self.dynamic_forces = not self.dynamic_forces

    def toggle_nontree_edge_display(self):
        self.display_non_tree_edges = not self.display_non_tree_edges
        if self.check_for_tree_layout() == True:
            self.regenerate(same_positions = True)

    def toggle_edge_segmentation(self):
        for e in self.scene.items():
            if e.__name__ == 'Edge':
                e.toggle_segmentation()
        self.scene.update()

    def toggle_edge_curving(self):
        for e in self.scene.items():
            if e.__name__ == 'Edge':
                e.toggle_curving()
        self.scene.update()

    def depth_first_search(self, root, index = 0):      # time complexity of DFS is O(2E) = O(E)
        root_id = root
        self.dfs = [(root_id, root_id)]
      #  self.max_depth = []
        visited = [root_id]
        self.depth_first_search_next(self.vertices[index][root_id], visited)
        if len(self.dfs) < len(self.vertices[index].keys()):
            print("WARNING: There are", len(self.vertices[index].keys()) - len(self.dfs),"nodes in the",self.layout, "graph that are not connected with the rest, these are currently not displayed")

        # if main.printing_mode:
        #     print("dfs order:",self.dfs)

        self.dfs_list.append(self.dfs)

        return self.dfs
        
    def depth_first_search_exhaustive(self, dfs_trees = None, root = "most connected", given_root_id = None, visited = None, index = 0):      # time complexity of DFS is O(2E) = O(E)
        if given_root_id != None:
            root_id = given_root_id
        elif root == "most connected":
            root_id = main.most_connected_node_id
        else:
            raise ValueError ("No root given for exhaustive dfs")
        
        if dfs_trees == None:
            dfs_trees = []
        self.dfs = [(root_id, root_id)]
        if visited == None:
            visited = [root_id]
        else:
            visited.append(root_id)
            # print("appending",root_id,"to visited")
        self.depth_first_search_next(self.vertices[index][root_id], visited)

        dfs_trees.append(self.dfs)

        if len(visited) < len(self.vertices[index].keys()):
            #print("There are", len(self.vertices[index].keys()) - len(visited),"nodes in the",self.layout, "(sub)graph that are not connected with the rest, making new dfs")
            for node_id in self.vertices[index].keys():
                if node_id not in visited:
                    new_root = node_id
                    #print("new root is",new_root)
                    break
            # print("visited list is",visited)

            self.depth_first_search_exhaustive(dfs_trees, given_root_id = new_root, visited = visited)
        else:
            # if main.printing_mode:
            #     print("exhaustive dfs order:",self.dfs_trees)
            self.dfs_trees = dfs_trees
            self.dfs = dfs_trees[0]
            print("exhaustive dfs order:",self.dfs_trees)
        return self.dfs_trees
    
    #global max_depth
    def depth_first_search_next(self, vertex, visited):  
       # self.dfs.append(vertex.id)
        for (edge, next) in vertex.edges:
            if next.id not in visited:
                self.dfs.append((vertex.id, next.id))
                visited.append(next.id)
                self.depth_first_search_next(next, visited)

    def breadth_first_search(self, root = "most connected", index = 0):
        if root == "most connected":
            root_id = main.most_connected_node_id
        else:
            root_id = root
        self.bfs = []
        queue = [(root_id, root_id)]
        visited = [root_id]
        while queue:
            vertex_id, parent_id = queue.pop() # remove first vertex of the queue -> pop(0)
            if main.printing_mode:
                print("Vertex_id, parent_id: ", vertex_id, parent_id)
            self.bfs.append((parent_id, vertex_id)) #keep track of the visited vertices
            for (edge, next) in self.vertices[index][vertex_id].edges:
                if next.id not in visited: #if vertex not visited, append to visited
                    visited.append(next.id)
                    queue.append((next.id, vertex_id)) # its ID and

        if main.printing_mode:
            print("bfs order:", self.bfs)

        if len(self.bfs) < len(self.vertices[index].keys()):
            print("WARNING: There are", len(self.vertices[index].keys()) - len(self.bfs),"nodes in the",self.layout, "graph that are not connected with the rest, these are currently not displayed")

        self.bfs_list.append(self.bfs)
            
        return self.bfs



    def prims_algorithm(self, root = "most connected", index = 0):
        if root == "most connected":
            root_id = main.most_connected_node_id
        else:
            root_id = root

        self.prims = [(root_id, root_id)]
        visited = [root_id] 
        distances = {}
        #distances = queue.PriorityQueue()  maybe change it to priorityqueue after it's done for performance reasons
        for (edge, next) in self.vertices[index][root_id].edges:
            distances[next.id] = (edge.weight, root_id)     # (distance, parent)

        while (len(self.prims) != len(self.vertices[index].keys())):       # make sure no duplicates go into self.prims
            if len(distances.keys()) == 0:      # if there are no more vertices to check (dictionary is empty)
                print("WARNING: There are",len(self.vertices[index].keys()) - len(self.prims),"nodes in the",self.layout, "graph that are not connected with the rest, these are currently not displayed")
                break
                #raise ValueError ("There are nodes in the graph that are not connected with the rest")
                # TODO: handle this situation, maybe make a new tree with an unused node as new root

            min_dist = None
            min_node_id = None
            min_node_parent = None

            for node_id, (distance, parent) in distances.items():      # find minimum weight among nodes connected to MST
                if (min_dist == None)  or (min_dist > distance):
                    min_dist = distance
                    min_node_id = node_id
                    min_node_parent = parent
            self.prims.append((min_node_parent, min_node_id))
            visited.append(min_node_id)

            del distances[min_node_id]

            for (edge, next) in self.vertices[index][min_node_id].edges:   # add new neighbours of new mst node to checking dictionary
                if next.id not in visited:
                    distances[next.id] = (edge.weight, min_node_id)

        if main.printing_mode:
            print("prims order:", self.prims)

        self.prims_list.append(self.prims)

        return self.prims



        


if __name__ == "__main__":

    # Qt Application
    app = QApplication(sys.argv)

    window = MainWindow(main.adjacency_dict_list, "force random", default_radius=10)
    window.show()

    

    sys.exit(app.exec())