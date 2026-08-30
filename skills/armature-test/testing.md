# Tests and Mocking

## Good tests

Test through real interfaces, not mocks of internal parts.

```python
# GOOD: observable behavior through the node's public topics
def test_estop_halts_commanded_motion(harness):
    harness.launch(MotionGate)
    harness.publish("/cmd_vel", twist(linear_x=0.5))
    harness.publish("/estop", Bool(data=True))
    assert harness.last_message("/wheel_cmd").linear.x == 0.0
```

Characteristics:

- Tests behavior callers care about
- Uses the public interface only
- Survives internal refactors
- Describes WHAT, not HOW
- One logical assertion per test

## Bad tests

**Implementation-detail tests**: coupled to internal structure.

```python
# BAD: asserts on an internal collaborator
def test_estop_engages_brake_controller():
    node = MotionGate()
    node.brake_controller = Mock()
    node.on_estop(Bool(data=True))
    node.brake_controller.engage.assert_called_once()
```

Red flags:

- Mocking internal collaborators
- Testing private methods or private state
- Asserting on call counts/order
- Test breaks when refactoring without behavior change
- Test name describes HOW not WHAT
- Verifying through a side channel instead of the interface

```python
# BAD: reaches into private state to verify
def test_odometry_integrates_ticks():
    node = OdometryNode()
    node.on_wheel_ticks(ticks(left=100, right=100))
    assert node._pose.x > 0

# GOOD: verifies through the published interface
def test_odometry_integrates_ticks(harness):
    harness.launch(OdometryNode)
    harness.publish("/wheel_ticks", ticks(left=100, right=100))
    assert harness.last_message("/odom").pose.position.x == approx(0.157, abs=1e-3)
```

**Tautological tests**: the expected value restates the implementation, so the test passes by construction.

```python
# BAD: expected wrench recomputed the way the code computes it
def test_gravity_compensation():
    q = [0.0, 1.57, 0.0]
    expected = jacobian(q).T @ gravity_load(q)
    assert compensator.torques(q) == approx(expected)

# GOOD: expected value from an independent source of truth
def test_gravity_compensation():
    q = [0.0, 1.57, 0.0]  # worked example, analysis/derivation/gravity-comp.md
    assert compensator.torques(q) == approx([0.0, 14.2, 0.31], abs=0.05)
```

In an Armature project the independent sources of truth are the derivation notes and model in `analysis/`, cached datasheets, and hand-worked examples — never the code under test.

## When to mock

Mock at the **hardware boundary** only:

- HAL and device drivers
- Transport (serial, CAN, I2C, SPI, network)
- Clock and time sources
- Randomness

Don't mock:

- Your own modules
- Internal collaborators
- Anything you control

**Simulation is the mock of the world.** Physics, contact, sensor streams: when an assertion needs the world to answer, that's a sim test, not a hand-rolled mock of physics.

```cpp
// Driver tested against a fake bus at the hardware boundary
TEST(ImuDriver, ReportsScaledAcceleration) {
  FakeI2cBus bus;
  bus.load_register(ACCEL_XOUT_H, {0x40, 0x00});  // +1 g raw, per datasheet
  ImuDriver imu(bus, Range::G2);
  EXPECT_NEAR(imu.read().accel_x, 9.81, 0.01);
}
```

## Designing for mockability

At the hardware boundary, design interfaces that are easy to fake:

**1. Inject the device, clock, and randomness**

```cpp
// Easy to fake: the bus is injected
ImuDriver(I2cBus& bus, Range range);

// Hard to fake: the driver opens the real device itself
ImuDriver(Range range) : bus_(open_i2c("/dev/i2c-1")) {}
```

A controller that reads the wall clock internally can't run under a fixed-timestep sim test; take the clock as a parameter.

**2. Give every external device an explicit driver interface**

Specific methods per operation, not a generic frame passthrough:

```python
# GOOD: each operation independently fakeable
class GripperDriver(Protocol):
    def command_width(self, meters: float) -> None: ...
    def read_width(self) -> float: ...
    def read_current(self) -> float: ...

# BAD: faking requires decoding raw frames inside the fake
class Gripper:
    def send(self, can_frame: bytes) -> bytes: ...
```

The explicit interface means each fake returns one specific shape, test setup has no conditional logic, and a test shows at a glance which device operations it exercises.
