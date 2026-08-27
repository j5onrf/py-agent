class PhysicsEngine:
    def __init__(self, gravity=9.81, air_resistance=0.01):
        self.gravity = gravity
        self.air_resistance = air_resistance
        self.objects = []

    def add_object(self, obj_id, mass, initial_velocity):
        self.objects.append(
            {"id": obj_id, "mass": mass, "velocity": initial_velocity, "pos": 0.0}
        )

    def calculate_kinetic_energy(self, mass, velocity):
        """Calculates kinetic energy: 0.5 * m * v^2"""
        return 0.5 * mass * (velocity**2)

    def calculate_potential_energy(self, mass, height):
        """Calculates potential energy: m * g * h"""
        return mass * self.gravity * height

    def calculate_drag_force(self, velocity, area, drag_coefficient=0.47):
        """Calculates drag force on an object moving through fluid."""
        return 0.5 * drag_coefficient * 1.225 * area * (velocity**2)

    def compute_trajectory(self, v0, angle_degrees, time_step=0.1, total_time=10.0):
        """Simulates 2D projectile trajectory over time."""
        import math

        angle_rad = math.radians(angle_degrees)
        vx = v0 * math.cos(angle_rad)
        vy = v0 * math.sin(angle_rad)
        trajectory = []
        t = 0.0
        x, y = 0.0, 0.0
        while t <= total_time and y >= 0:
            trajectory.append((t, round(x, 2), round(y, 2)))
            x += vx * time_step
            vy -= self.gravity * time_step
            y += vy * time_step
            t += time_step
        return trajectory
