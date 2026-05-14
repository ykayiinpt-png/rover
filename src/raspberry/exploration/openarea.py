from datetime import datetime, timezone
import json
import math
from collections import deque
from typing import List, Tuple, Optional

class OpenAreaExplorer:
    """
    Simple and robust 360° open-area explorer.

    Principle
    ---------
    1. Collect (angle, distance)
    2. Keep only open points
    3. Group neighboring angles into sectors
    4. Select the widest sector
    5. Inside that sector:
         choose the point with maximum distance

    Designed for noisy IMU scans with irregular gaps.
    """

    def __init__(
        self,
        open_distance_threshold: float = 0.25,
        min_sector_size_deg: float = 20.0,
        max_angle_gap_deg: float = 30.0,
        filter_window_size: int = 3,
    ):

        # Raw samples
        self.samples: List[Tuple[float, float]] = []

        # Threshold to consider area open
        self.open_distance_threshold = (
            open_distance_threshold
        )

        # Minimum valid sector width
        self.min_sector_size_rad = math.radians(
            min_sector_size_deg
        )

        # Maximum gap between points
        self.max_angle_gap_rad = math.radians(
            max_angle_gap_deg
        )

        # Distance smoothing
        self.front_history = deque(
            maxlen=filter_window_size
        )

        self.best_heading_angle = 0.0

    # =====================================================
    # ANGLES
    # =====================================================

    @staticmethod
    def normalize_angle(angle: float) -> float:
        """
        Normalize angle to [-pi, pi]
        """

        while angle > math.pi:
            angle -= 2 * math.pi

        while angle < -math.pi:
            angle += 2 * math.pi

        return angle

    @staticmethod
    def angular_distance(a: float, b: float) -> float:
        """
        Smallest circular angular distance
        """

        diff = a - b

        return math.atan2(
            math.sin(diff),
            math.cos(diff)
        )

    # =====================================================
    # FILTER
    # =====================================================

    def filter_distance(
        self,
        distance: float
    ) -> float:

        self.front_history.append(distance)

        return (
            sum(self.front_history) /
            len(self.front_history)
        )

    # =====================================================
    # INPUT
    # =====================================================

    def add_sample(
        self,
        imu_angle: float,
        front_distance: float,
    ):
        """
        Add scan sample
        """

        imu_angle = self.normalize_angle(
            imu_angle
        )

        filtered_distance = self.filter_distance(
            front_distance
        )

        self.samples.append(
            (
                imu_angle,
                filtered_distance
            )
        )

    # =====================================================
    # DETECT OPEN SECTORS
    # =====================================================

    def _detect_open_sectors(
        self,
        samples
    ):
        """
        Detect continuous open sectors
        """

        open_sectors = []

        current_sector = []

        previous_angle = None

        for angle, distance in samples:

            # Ignore blocked points
            if (
                distance <
                self.open_distance_threshold
            ):

                if current_sector:

                    open_sectors.append(
                        current_sector
                    )

                    current_sector = []

                previous_angle = None

                continue

            # First point
            if previous_angle is None:

                current_sector = [
                    (angle, distance)
                ]

                previous_angle = angle

                continue

            # Circular angular gap
            gap = abs(
                self.angular_distance(
                    angle,
                    previous_angle
                )
            )

            # New sector if gap too large
            if gap > self.max_angle_gap_rad:

                if current_sector:

                    open_sectors.append(
                        current_sector
                    )

                current_sector = [
                    (angle, distance)
                ]

            else:

                current_sector.append(
                    (angle, distance)
                )

            previous_angle = angle

        # Final sector
        if current_sector:

            open_sectors.append(
                current_sector
            )

        return open_sectors

    # =====================================================
    # SECTOR WIDTH
    # =====================================================

    def _sector_width(
        self,
        sector
    ) -> float:
        """
        Compute sector angular width
        """

        if len(sector) < 2:
            return 0.0

        angles = [
            a for a, _ in sector
        ]

        angles = sorted(angles)

        width = 0.0

        for i in range(1, len(angles)):

            width += abs(
                self.angular_distance(
                    angles[i],
                    angles[i - 1]
                )
            )

        return width

    # =====================================================
    # MAIN
    # =====================================================

    def get_best_heading(
        self
    ) -> Optional[float]:
        """
        Compute best escape heading
        """

        if len(self.samples) < 3:
            return None

        # Sort by angle
        samples = sorted(
            self.samples,
            key=lambda x: x[0]
        )

        # Detect sectors
        open_sectors = (
            self._detect_open_sectors(
                samples
            )
        )

        if not open_sectors:
            return None

        # Keep valid sectors
        valid_sectors = []

        for sector in open_sectors:
            width = self._sector_width(sector)

            if width >= self.min_sector_size_rad:
                valid_sectors.append( sector)

        if not valid_sectors:
            return None

        # Select widest sector
        best_sector = max(
            valid_sectors,
            key=lambda s:
                self._sector_width(s)
        )

        # Inside sector:
        # choose max distance point
        best_angle, _ = max(
            best_sector,
            key=lambda x: x[1]
        )
        
        angles = [
            a for a, _ in best_sector
        ]

        x = sum(math.cos(a) for a in angles)
        y = sum(math.sin(a) for a in angles)

        best_angle = math.atan2(y, x)

        self.best_heading_angle = (
            self.normalize_angle(
                best_angle
            )
        )
        
        self.save_data()

        return self.best_heading_angle

    def clear(self):
        """
        Clear all scan data
        """

        self.samples.clear()
        self.front_history.clear()
        
    def save_data(self):
        """
        Save scan data to a JSON file
        """

        data = {
            "open_distance_threshold": self.open_distance_threshold,
            "min_sector_size_rad": self.min_sector_size_rad,
            "best_angle": self.best_heading_angle,
            "samples": [
                {
                    "angle": angle,
                    "distance": distance
                }
                for angle, distance in self.samples
            ]
        }

        with open(f"openarea_{datetime.now(timezone.utc).timestamp()}.json", "w") as f:
            json.dump(data, f, indent=4)
            
    def load_data(self, filepath: str):
        """
        Load scan data from a JSON file
        """

        with open(filepath, "r") as f:
            data = json.load(f)

        self.samples = [
            (item["angle"], item["distance"])
            for item in data["samples"]
        ]

        self.open_distance_threshold = data.get(
            "open_distance_threshold",
            self.open_distance_threshold
        )

        self.min_sector_size_rad = data.get(
            "min_sector_size_rad",
            self.min_sector_size_rad
        )
