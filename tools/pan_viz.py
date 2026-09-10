import tkinter as tk
from tkinter import Canvas, Scrollbar, Frame
import random
import math
import threading
import time
from typing import List, Dict, Any, Optional
import sys
import os

# Add path to PAN_SDK for import
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'PAN_SDK'))
from PAN_SDK import (
    SovereignIdentity, DHTNode, PANCitizenRegistry, PANEconomicEngine,
    PANNameRegistry, utc_now_iso, sha256_hex
)

# Sacred ratio constants for harmonics
PHI = (1 + math.sqrt(5)) / 2
TAU = 2 * math.pi

class GridVisualizer:
    def __init__(self, num_nodes: int = 10, dht_node: Optional[DHTNode] = None,
                 citizen_registry: Optional[PANCitizenRegistry] = None):
        self.root = tk.Tk()
        self.root.title("PAN Grid – Sovereign Territory")
        
        # Main frame with scrollbar for large grids
        self.main_frame = Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        self.canvas = Canvas(self.main_frame, width=1200, height=800, bg='black')
        self.scrollbar_y = Scrollbar(self.main_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollbar_x = Scrollbar(self.main_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.scrollbar_y.set, xscrollcommand=self.scrollbar_x.set)
        self.scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Bind mouse events for zooming/panning
        self.canvas.bind("<MouseWheel>", self._zoom)
        self.canvas.bind("<B1-Motion>", self._pan)
        self.canvas.bind("<Button-1>", self._select_node)
        self.zoom_factor = 1.0
        self.pan_x, self.pan_y = 0, 0
        
        # Integration with PAN_SDK
        self.dht_node = dht_node or self._init_pan_components(num_nodes)
        self.citizen_registry = citizen_registry or self.dht_node.citizen_registry
        self.economic_engine = self.dht_node.economic_engine
        self.name_registry = self.dht_node.name_registry
        
        # Nodes from PAN data
        self.nodes: List[Dict[str, Any]] = []
        self.connections: List[Dict[str, Any]] = []
        self.selected_node: Optional[Dict[str, Any]] = None
        
        # Animation state
        self.animation_running = True
        self.phase = 0.0  # For sacred ratio harmonics
        
        # Start data fetching and animation threads
        self.data_thread = threading.Thread(target=self._fetch_pan_data, daemon=True)
        self.data_thread.start()
        self.animate()
    
    def _init_pan_components(self, num_nodes: int) -> DHTNode:
        """Initialize minimal PAN components for viz."""
        identity = SovereignIdentity("GridVizIdentity")
        dht = DHTNode(identity, enable_consensus=False, enable_registries=True)
        # Seed with some test citizens
        for i in range(num_nodes):
            test_identity = SovereignIdentity(f"TestCitizen{i}")
            dht.citizen_registry.register_citizen(test_identity, citizen_type="standard")
            # Add some tokens
            if dht.economic_engine:
                dht.economic_engine.mint_tokens(test_identity.identity_hash, random.randint(10, 100), "viz_init")
        return dht
    
    def _fetch_pan_data(self):
        """Thread to fetch live data from PAN."""
        while self.animation_running:
            # Fetch citizens and their data
            citizens = []
            for citizen_id in self.citizen_registry.citizens:
                citizen = self.citizen_registry.citizens[citizen_id]
                balance = self.economic_engine.get_balance(citizen.identity_hash) if self.economic_engine else 0
                names = self.name_registry.resolve_identity_names(citizen.identity_hash) if self.name_registry else []
                citizens.append({
                    "id": citizen.citizen_id,
                    "identity_hash": citizen.identity_hash,
                    "x": random.randint(50, 1150),
                    "y": random.randint(50, 750),
                    "tokens": balance,
                    "active": citizen.active_status,
                    "names": names,
                    "reputation": citizen.reputation_score
                })
            self.nodes = citizens
            
            # Build connections (e.g., based on shared apps or governance)
            self.connections = []
            for i, node1 in enumerate(self.nodes):
                for j, node2 in enumerate(self.nodes[i+1:], start=i+1):
                    if random.random() < 0.1:  # Simulate connections
                        self.connections.append({"from": node1, "to": node2})
            
            time.sleep(5)  # Refresh every 5s
    
    def _zoom(self, event):
        """Handle zoom with mouse wheel."""
        scale = 1.1 if event.delta > 0 else 0.9
        self.zoom_factor *= scale
        self.canvas.scale("all", event.x, event.y, scale, scale)
    
    def _pan(self, event):
        """Handle panning."""
        if hasattr(self, 'last_x') and hasattr(self, 'last_y'):
            dx, dy = event.x - self.last_x, event.y - self.last_y
            self.canvas.move("all", dx, dy)
        self.last_x, self.last_y = event.x, event.y
    
    def _select_node(self, event):
        """Select node on click for details."""
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        for node in self.nodes:
            if math.hypot(node["x"] - x, node["y"] - y) < 15:
                self.selected_node = node
                self._show_node_details(node)
                break
    
    def _show_node_details(self, node: Dict[str, Any]):
        """Display details of selected node."""
        details = f"ID: {node['id']}\nHash: {node['identity_hash'][:12]}...\nTokens: {node['tokens']}\nNames: {', '.join(node['names'])}\nReputation: {node['reputation']}"
        self.canvas.create_text(600, 50, text=details, fill="white", font=("Courier", 10), anchor="nw", tags="details")
    
    def animate(self):
        if not self.animation_running:
            return
        
        self.canvas.delete("all")
        self.phase += 0.1  # Sacred ratio phase increment
        
        # Draw connections
        for conn in self.connections:
            x1, y1 = conn["from"]["x"], conn["from"]["y"]
            x2, y2 = conn["to"]["x"], conn["to"]["y"]
            self.canvas.create_line(x1, y1, x2, y2, fill="gray", width=1, dash=(5, 5))
        
        # Draw nodes with harmonics
        for node in self.nodes:
            if node["active"]:
                # Harmonic modulation for size/color
                harmonic = math.sin(PHI * self.phase) * math.cos(TAU * self.phase / PHI)
                size = 10 + 5 * harmonic
                intensity = int(255 * (0.5 + 0.5 * harmonic))
                color = f"#{intensity:02x}{intensity:02x}ff" if node["tokens"] > 50 else f"#{intensity:02x}ff{intensity:02x}"
                
                self.canvas.create_oval(node["x"]-size, node["y"]-size, node["x"]+size, node["y"]+size, 
                                        fill=color, outline="white")
                self.canvas.create_text(node["x"], node["y"]-20, text=f"{node['id']} ({node['tokens']}t)", 
                                        fill="white", font=("Arial", 8))
                
                # Hashchain trail with sacred ratio
                trail_length = 20
                for i in range(trail_length):
                    offset = i * PHI
                    tx = node["x"] + math.sin(self.phase + offset) * 10
                    ty = node["y"] + math.cos(self.phase + offset) * 10
                    alpha = 1 - i / trail_length
                    trail_color = f"#{int(255*alpha):02x}00ff"
                    self.canvas.create_oval(tx-2, ty-2, tx+2, ty+2, fill=trail_color, outline="")
        
        # Status readout
        total_tokens = sum(n["tokens"] for n in self.nodes)
        active_count = len([n for n in self.nodes if n["active"]])
        status = f"Sovereign Grid: {active_count} active citizens | Total Tokens: {total_tokens} | Φ Phase: {self.phase:.2f} | End of line."
        self.canvas.create_text(600, 780, text=status, fill="green", font=("Courier", 12))
        
        self.root.after(100, self.animate)  # Faster animation
    
    def run(self):
        self.root.mainloop()
        self.animation_running = False

# Usage
if __name__ == "__main__":
    viz = GridVisualizer(15)
    viz.run()