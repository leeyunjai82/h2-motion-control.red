# Installation Guide (INSTALL) — Ubuntu

A step-by-step procedure for installing the Unitree G1 Motion Control project on **Ubuntu (22.04 LTS recommended)**. Follow each step in order.

- Usage : [`README.md`](./README.md)
- Internals (architecture, motion JSON schema, IK, DDS, FSM) : [`TECH.md`](./TECH.md)

---

## 1. System Requirements

| Item | Recommended |
| --- | --- |
| OS | Ubuntu 22.04 LTS (20.04 LTS also supported) |
| Python | 3.10 (via Miniconda) |
| Memory | 8 GB or more |
| Disk | 10 GB free space or more |
| Network | Same LAN as the G1 robot (wired recommended) |
| Camera | Intel RealSense D435i (USB 3.0) |
| Privileges | An account with sudo access |

Default install path: `/home/<user>/project/g1-motion-control/`

> ℹ️ Replace `<user>` with your actual account name (e.g. `pion`). Do **not** hard-code an account name into scripts or sudoers — see step 8 and the Troubleshooting section on account migration.

> ℹ️ The RealSense apt repository officially supports 20.04 / 22.04. On 24.04 you may need to build librealsense from source.

---

## 2. Base OS Packages

Install build tools, USB/camera libraries, and OpenGL components first.

```bash
sudo apt update
sudo apt install -y \
    build-essential \
    git wget curl \
    cmake pkg-config \
    libusb-1.0-0-dev \
    libgl1-mesa-dev libglu1-mesa-dev \
    libglvnd-dev \
    libglfw3 libglfw3-dev \
    python3-dev
```

---

## 3. Intel RealSense SDK

System libraries required by the RealSense D435i camera.

```bash
# Register Intel's signing key and apt repo
sudo mkdir -p /etc/apt/keyrings
curl -sSf https://librealsense.intel.com/Debian/librealsense.pgp \
    | sudo tee /etc/apt/keyrings/librealsense.pgp > /dev/null

echo "deb [signed-by=/etc/apt/keyrings/librealsense.pgp] \
https://librealsense.intel.com/Debian/apt-repo $(lsb_release -cs) main" \
    | sudo tee /etc/apt/sources.list.d/librealsense.list

sudo apt update
sudo apt install -y librealsense2-dkms librealsense2-utils librealsense2-dev
```

After installation, connect the camera to a USB 3.0 port and verify:

```bash
realsense-viewer
```

> ℹ️ `realsense-viewer` and `rs-enumerate-devices` are provided by `librealsense2-utils`. If those commands are missing, that package was not installed. You can still verify the camera from Python with `pyrealsense2` (see step 11).

---

## 4. Miniconda Installation

Use a Miniconda environment to avoid affecting the system Python.

```bash
cd ~
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh -b -p $HOME/miniconda3
source $HOME/miniconda3/bin/activate
conda init bash
```

Open a new terminal and confirm with `conda --version`.

---

## 5. Create the `tv` Environment

This project uses a conda environment named `tv`.
(The scripts call `conda activate tv` internally, so keep the name.)

```bash
conda create -n tv python=3.10 -y
conda activate tv
```

> ⚠️ If you see `CondaToSNonInteractiveError` (Terms of Service not accepted), run:
> ```bash
> conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
> conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
> ```
> then retry the `conda create` command.

---

## 6. Clone the Project

```bash
mkdir -p $HOME/project
cd $HOME/project
git clone https://github.com/leeyunjai82/g1-motion-control.git
cd g1-motion-control
```

---

## 7. Install Python Packages

`requirements.txt` defines roughly 100 packages, including FastAPI, OpenCV, PyTorch, MuJoCo, Ultralytics (YOLO), pyrealsense2, CycloneDDS, and the Unitree SDK.

Install a few system libraries required to build native wheels first:

```bash
# For cyclonedds
sudo apt install -y libssl-dev bison flex
# For scikit-sparse (provides cholmod.h)
sudo apt install -y libsuitesparse-dev
```

Then install the Python packages:

```bash
conda activate tv
pip install --upgrade pip
pip install -r requirements.txt
```

> ⚠️ `unitree_sdk2py` is installed directly from GitHub (`-e git+...`).
> If the network is restricted, you will need an internal mirror or an offline wheel package.

> ⚠️ **NumPy must stay on the 1.x line.** OpenCV 4.10 wheels are built against the NumPy 1.x ABI. If NumPy 2.x is pulled in, `cv2.imencode` (and other OpenCV calls) will raise
> `error: (-5:Bad argument) ... img is not a numpy array`
> even for a valid array. After installing requirements, verify and pin if needed:
> ```bash
> python -c "import numpy; print(numpy.__version__)"   # must be < 2
> pip install "numpy<2"                                 # if it shows 2.x
> ```

---

## 8. Sudo Configuration (for FSM Script)

`start_fsm.sh` runs Python with `sudo` because motor control requires elevated privileges. To avoid typing a password each time, add a NOPASSWD rule via `visudo`.

```bash
sudo visudo
```
Add (replace `<user>` with your account name):
```
<user> ALL=(ALL) NOPASSWD: /home/<user>/miniconda3/envs/tv/bin/python
```

> ⚠️ **The command path in this rule must match exactly** the interpreter the scripts run. The NOPASSWD rule only applies when the full path matches; if the username or path differs (e.g. left over from a previous account), sudo will silently prompt for a password and the FSM script will hang or fail. See the account-migration note in Troubleshooting.

Verify:
```bash
sudo /home/<user>/miniconda3/envs/tv/bin/python -c "print('ok')"   # should NOT prompt for a password
```

---

## 9. Network Setup

The G1 robot's default IP is `192.168.123.161`. Set the PC's wired LAN to the same subnet.

```bash
# Example: assign 192.168.123.222/24 to interface enp3s0
sudo nmcli connection modify "<connection-name>" ipv4.addresses 192.168.123.222/24
sudo nmcli connection modify "<connection-name>" ipv4.method manual
sudo nmcli connection up "<connection-name>"
```

Verify:
```bash
ping 192.168.123.161
```

---

## 10. Performance: Pin BLAS Threads (Important)

The dual-arm IK (pinocchio + CasADi, 14 DOF) solves small linear systems. On multi-threaded OpenBLAS builds, thread synchronization overhead **dominates** these small problems and can slow a single IK solve from ~1.5 ms to ~40 ms (roughly 28x). Forcing a single BLAS thread fixes this.

Set the thread limits **before NumPy is imported**. Two complementary places:

**(a) conda environment activation hook** — applies whenever the `tv` env is activated:

```bash
mkdir -p $HOME/miniconda3/envs/tv/etc/conda/activate.d
cat > $HOME/miniconda3/envs/tv/etc/conda/activate.d/threads.sh << 'EOF'
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
EOF
```

**(b) start scripts** — so the limit applies no matter which environment launches them. Add near the top of `start_*.sh` (after `set -u`):

```bash
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
```

> ⚠️ `sudo` resets the environment, so exports in a shell do **not** reach a `sudo python ...` child. For FSM/motor processes launched with sudo, set the variables inline on the sudo line:
> ```bash
> sudo OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
>     /home/<user>/miniconda3/envs/tv/bin/python "$SCRIPT_DIR/utils/init_fsm.py" "$1"
> ```

Confirm after activation:
```bash
conda activate tv
echo $OMP_NUM_THREADS   # should print 1
```

---

## 11. Grant Execute Permissions

```bash
cd $HOME/project/g1-motion-control
chmod +x start_fsm.sh start_box.sh start_grab.sh start_motion.sh activate_tv.sh
```

---

## 12. Verify the Installation

If the following all succeed, installation is complete.

```bash
# (1) Activate environment
source activate_tv.sh

# (2) Check core Python packages (including pinocchio for IK)
python -c "import numpy, cv2, torch, pyrealsense2, pinocchio, unitree_sdk2py; print('OK')"

# (3) Confirm NumPy is on the 1.x line and OpenCV encode works
python -c "
import numpy as np, cv2
assert np.__version__ < '2', f'NumPy {np.__version__} — must be < 2'
ok, _ = cv2.imencode('.jpg', np.zeros((480,640,3), np.uint8))
print('numpy', np.__version__, 'imencode', ok)
"

# (4) Check RealSense
python -c "import pyrealsense2 as rs; print(rs.context().devices[0].get_info(rs.camera_info.name))"

# (5) (Optional) Benchmark IK — expect a few ms with threads pinned
python -c "
import time, numpy as np, pinocchio as pin
from high.ctrl.robot_arm_ik import G1_29_ArmIK
ik = G1_29_ArmIK(); q=np.zeros(14); dq=np.zeros(14)
L=pin.SE3(pin.Quaternion(1,0,0,0),np.array([0.3, 0.2,0.1])).homogeneous
R=pin.SE3(pin.Quaternion(1,0,0,0),np.array([0.3,-0.2,0.1])).homogeneous
ik.solve_ik(L,R,q,dq)
t=time.time()
for _ in range(50): ik.solve_ik(L,R,q,dq)
print(f'IK avg: {(time.time()-t)/50*1000:.1f} ms')
"
```

If everything is OK, continue with [`README.md`](./README.md) for usage instructions, or [`TECH.md`](./TECH.md) for the internal architecture.

---

## Troubleshooting

| Symptom | Cause / Fix |
| --- | --- |
| `CondaToSNonInteractiveError` | Accept channel ToS (see step 5) and retry |
| `cyclonedds` build fails | Install `libssl-dev`, `bison`, `flex` and retry |
| `scikit-sparse` fails: `cholmod.h not found` | Install `libsuitesparse-dev`, or `conda install -c conda-forge scikit-sparse` |
| `cv2.imencode` / OpenCV: `img is not a numpy array` (valid array) | NumPy 2.x vs OpenCV 4.10 ABI mismatch. `pip install "numpy<2"` (see step 7) |
| IK / motion very slow (tens of ms per solve) | Multi-threaded BLAS overhead. Pin threads to 1 (see step 10) |
| RealSense not detected | Use a USB 3.0 port; verify with `realsense-viewer` (or `pyrealsense2`) first |
| `rs-enumerate-devices: command not found` | `librealsense2-utils` not installed; verify via `pyrealsense2` in Python instead |
| `Permission denied` / sudo keeps prompting (FSM) | sudoers path does not match the interpreter. Check the NOPASSWD rule path (step 8) |
| `RuntimeError: class version St6vector...basic_string` on `pickle.load` | Stale pinocchio model cache from a different pinocchio version. Delete/rename the cache (e.g. `high/ctrl/g1_29_model_cache.pkl`) and let it regenerate |
| Zombie processes remain | Clean up with `pkill -9 -f rs_stream.py` (etc.) and restart |

### Account / Path Migration (e.g. moving from one user to another)

If the project was set up under a different account and the home directory changed (for example `/home/olduser` → `/home/newuser`), check for leftover hard-coded paths:

```bash
# Find any remaining references to the old account name
grep -rn "/home/<olduser>" $HOME/project/g1-motion-control/
```

Things that commonly break after a home-directory change:

1. **sudoers NOPASSWD rule** — still points at the old path, so sudo silently prompts for a password and FSM/motor scripts fail. Fix with `visudo` (step 8) using the new path.
2. **pinocchio model cache (`*.pkl`)** — a cache built under the old environment can fail to unpickle if the pinocchio version also changed (`class version ...` error). Delete it and let it rebuild.
3. **Comments / docs** — references in `INSTALL.md` and `# location:` header comments in `start_*.sh` are harmless, but update them to avoid confusion.

Scripts that use `$HOME`, `$SCRIPT_DIR`, or `$(dirname "$0")` adapt automatically to the new account and do not need editing.


---
---
---


# 설치 가이드 (한국어) — Ubuntu

Unitree G1 Motion Control 프로젝트를 **Ubuntu (22.04 LTS 권장)** 에 설치하는 절차입니다. 순서대로 따라가시면 됩니다.

- 사용법 : [`README.md`](./README.md)
- 내부 구조 (아키텍처, 모션 JSON 스키마, IK, DDS, FSM) : [`TECH.md`](./TECH.md)

---

## 1. 시스템 요구사항

| 항목 | 권장 사양 |
| --- | --- |
| OS | Ubuntu 22.04 LTS (20.04 LTS 도 지원) |
| Python | 3.10 (Miniconda 환경 사용) |
| 메모리 | 8 GB 이상 |
| 디스크 | 10 GB 이상 여유 공간 |
| 네트워크 | G1 로봇과 동일한 LAN (유선 권장) |
| 카메라 | Intel RealSense D435i (USB 3.0) |
| 권한 | sudo 권한이 있는 계정 |

설치 기본 경로는 `/home/<사용자>/project/g1-motion-control/` 입니다.

> ℹ️ `<사용자>` 는 실제 계정명(예: `pion`)으로 바꿔서 사용하세요. 계정명을 스크립트나 sudoers 에 **하드코딩하지 마세요** — 8번 단계와 문제 해결의 계정 이관 항목을 참고하세요.

> ℹ️ RealSense apt 저장소는 20.04 / 22.04 를 공식 지원합니다. 24.04 에서는 librealsense 를 소스에서 직접 빌드해야 할 수 있습니다.

---

## 2. OS 기본 패키지 설치

빌드 도구, USB/카메라 라이브러리, OpenGL 등을 먼저 설치합니다.

```bash
sudo apt update
sudo apt install -y \
    build-essential \
    git wget curl \
    cmake pkg-config \
    libusb-1.0-0-dev \
    libgl1-mesa-dev libglu1-mesa-dev \
    libglvnd-dev \
    libglfw3 libglfw3-dev \
    python3-dev
```

---

## 3. Intel RealSense SDK 설치

RealSense D435i 카메라를 사용하기 위한 시스템 라이브러리입니다.

```bash
# Intel 서명 키와 apt 저장소 등록
sudo mkdir -p /etc/apt/keyrings
curl -sSf https://librealsense.intel.com/Debian/librealsense.pgp \
    | sudo tee /etc/apt/keyrings/librealsense.pgp > /dev/null

echo "deb [signed-by=/etc/apt/keyrings/librealsense.pgp] \
https://librealsense.intel.com/Debian/apt-repo $(lsb_release -cs) main" \
    | sudo tee /etc/apt/sources.list.d/librealsense.list

sudo apt update
sudo apt install -y librealsense2-dkms librealsense2-utils librealsense2-dev
```

설치 후 카메라를 USB 3.0 포트에 연결하고 다음 명령으로 동작을 확인합니다.

```bash
realsense-viewer
```

> ℹ️ `realsense-viewer`, `rs-enumerate-devices` 는 `librealsense2-utils` 패키지에 포함됩니다. 명령이 없다면 해당 패키지가 설치되지 않은 것입니다. 이 경우 Python 의 `pyrealsense2` 로도 카메라를 확인할 수 있습니다(11번 단계).

---

## 4. Miniconda 설치

기본 시스템 Python 을 건드리지 않기 위해 Miniconda 가상 환경을 사용합니다.

```bash
cd ~
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh -b -p $HOME/miniconda3
source $HOME/miniconda3/bin/activate
conda init bash
```

새 터미널을 열고 `conda --version` 으로 정상 설치를 확인합니다.

---

## 5. 가상환경 `tv` 생성

본 프로젝트는 `tv` 라는 이름의 conda 환경을 사용합니다.
(스크립트 내부에서 `conda activate tv` 로 호출되므로 이름을 그대로 사용하세요.)

```bash
conda create -n tv python=3.10 -y
conda activate tv
```

> ⚠️ `CondaToSNonInteractiveError` (Terms of Service 미승인) 오류가 나면 다음을 실행하세요.
> ```bash
> conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
> conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
> ```
> 그 후 `conda create` 를 다시 실행합니다.

---

## 6. 프로젝트 클론

```bash
mkdir -p $HOME/project
cd $HOME/project
git clone https://github.com/leeyunjai82/g1-motion-control.git
cd g1-motion-control
```

---

## 7. Python 패키지 설치

`requirements.txt` 에는 약 100여 개의 패키지가 정의되어 있습니다. 주요 항목: FastAPI, OpenCV, PyTorch, MuJoCo, Ultralytics(YOLO), pyrealsense2, CycloneDDS, Unitree SDK 등.

네이티브 wheel 빌드에 필요한 시스템 라이브러리를 먼저 설치합니다.

```bash
# cyclonedds 용
sudo apt install -y libssl-dev bison flex
# scikit-sparse 용 (cholmod.h 제공)
sudo apt install -y libsuitesparse-dev
```

그 다음 Python 패키지를 설치합니다.

```bash
conda activate tv
pip install --upgrade pip
pip install -r requirements.txt
```

> ⚠️ `unitree_sdk2py` 는 GitHub 에서 직접 설치됩니다(`-e git+...`).
> 네트워크가 차단된 환경이라면 사내 미러 또는 오프라인 wheel 패키지가 별도로 필요합니다.

> ⚠️ **NumPy 는 반드시 1.x 대를 유지해야 합니다.** OpenCV 4.10 wheel 은 NumPy 1.x ABI 로 빌드되어 있어, NumPy 2.x 가 설치되면 정상 배열에 대해서도 `cv2.imencode` 등 OpenCV 호출이
> `error: (-5:Bad argument) ... img is not a numpy array`
> 오류를 냅니다. requirements 설치 후 확인하고 필요하면 고정하세요.
> ```bash
> python -c "import numpy; print(numpy.__version__)"   # 반드시 < 2
> pip install "numpy<2"                                 # 2.x 로 나오면 실행
> ```

---

## 8. sudo 권한 설정 (FSM 스크립트용)

`start_fsm.sh` 는 모터 권한 때문에 `sudo` 로 Python 을 실행합니다. 매번 비밀번호 입력을 피하려면 sudoers 에 NOPASSWD 규칙을 추가합니다.

```bash
sudo visudo
```
추가 내용 (`<사용자>` 를 실제 계정명으로 교체):
```
<사용자> ALL=(ALL) NOPASSWD: /home/<사용자>/miniconda3/envs/tv/bin/python
```

> ⚠️ **이 규칙의 명령 경로는 스크립트가 실행하는 인터프리터 경로와 정확히 일치해야 합니다.** 경로가 조금이라도 다르면(예: 이전 계정에서 넘어온 경로) NOPASSWD 가 적용되지 않아 sudo 가 조용히 비밀번호를 요구하고, FSM 스크립트가 멈추거나 실패합니다. 문제 해결의 계정 이관 항목을 참고하세요.

확인:
```bash
sudo /home/<사용자>/miniconda3/envs/tv/bin/python -c "print('ok')"   # 비밀번호를 묻지 않아야 정상
```

---

## 9. 네트워크 설정

G1 로봇의 기본 IP 는 `192.168.123.161` 입니다. PC 의 유선 LAN 을 동일 대역으로 설정합니다.

```bash
# 예시: enp3s0 인터페이스를 192.168.123.222/24 로 설정
sudo nmcli connection modify "<연결이름>" ipv4.addresses 192.168.123.222/24
sudo nmcli connection modify "<연결이름>" ipv4.method manual
sudo nmcli connection up "<연결이름>"
```

연결 확인:
```bash
ping 192.168.123.161
```

---

## 10. 성능: BLAS 스레드 고정 (중요)

양팔 IK(pinocchio + CasADi, 14 DOF)는 작은 선형계를 풉니다. 멀티스레드 OpenBLAS 빌드에서는 이런 작은 문제에 스레드 동기화 오버헤드가 **지배적**으로 작용해, IK 1회 풀이가 약 1.5 ms 에서 약 40 ms 로(약 28배) 느려질 수 있습니다. BLAS 스레드를 1개로 고정하면 해결됩니다.

스레드 제한은 **NumPy import 이전**에 설정해야 합니다. 상호 보완적인 두 위치에 넣습니다.

**(a) conda 환경 활성화 훅** — `tv` 환경을 activate 할 때마다 자동 적용:

```bash
mkdir -p $HOME/miniconda3/envs/tv/etc/conda/activate.d
cat > $HOME/miniconda3/envs/tv/etc/conda/activate.d/threads.sh << 'EOF'
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
EOF
```

**(b) start 스크립트** — 어떤 환경에서 실행하든 제한이 걸리도록. `start_*.sh` 상단(`set -u` 다음)에 추가:

```bash
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
```

> ⚠️ `sudo` 는 환경을 초기화하므로, 셸의 export 는 `sudo python ...` 자식 프로세스에 **전달되지 않습니다.** sudo 로 실행하는 FSM/모터 프로세스는 sudo 줄에 변수를 직접 지정하세요.
> ```bash
> sudo OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
>     /home/<사용자>/miniconda3/envs/tv/bin/python "$SCRIPT_DIR/utils/init_fsm.py" "$1"
> ```

활성화 후 확인:
```bash
conda activate tv
echo $OMP_NUM_THREADS   # 1 이 출력되어야 정상
```

---

## 11. 실행 권한 부여

```bash
cd $HOME/project/g1-motion-control
chmod +x start_fsm.sh start_box.sh start_grab.sh start_motion.sh activate_tv.sh
```

---

## 12. 설치 검증

다음이 정상 동작하면 설치 완료입니다.

```bash
# (1) 환경 활성화
source activate_tv.sh

# (2) 핵심 Python 패키지 확인 (IK용 pinocchio 포함)
python -c "import numpy, cv2, torch, pyrealsense2, pinocchio, unitree_sdk2py; print('OK')"

# (3) NumPy 1.x 및 OpenCV 인코딩 동작 확인
python -c "
import numpy as np, cv2
assert np.__version__ < '2', f'NumPy {np.__version__} — 반드시 < 2'
ok, _ = cv2.imencode('.jpg', np.zeros((480,640,3), np.uint8))
print('numpy', np.__version__, 'imencode', ok)
"

# (4) RealSense 확인
python -c "import pyrealsense2 as rs; print(rs.context().devices[0].get_info(rs.camera_info.name))"

# (5) (선택) IK 벤치마크 — 스레드 고정 시 수 ms 예상
python -c "
import time, numpy as np, pinocchio as pin
from high.ctrl.robot_arm_ik import G1_29_ArmIK
ik = G1_29_ArmIK(); q=np.zeros(14); dq=np.zeros(14)
L=pin.SE3(pin.Quaternion(1,0,0,0),np.array([0.3, 0.2,0.1])).homogeneous
R=pin.SE3(pin.Quaternion(1,0,0,0),np.array([0.3,-0.2,0.1])).homogeneous
ik.solve_ik(L,R,q,dq)
t=time.time()
for _ in range(50): ik.solve_ik(L,R,q,dq)
print(f'IK avg: {(time.time()-t)/50*1000:.1f} ms')
"
```

이상이 없으면 [`README.md`](./README.md) 의 사용 방법으로 이동하거나, 내부 구조가 궁금하다면 [`TECH.md`](./TECH.md) 를 참고하세요.

---

## 문제 해결 (Troubleshooting)

| 증상 | 원인 / 해결 |
| --- | --- |
| `CondaToSNonInteractiveError` | 채널 ToS 승인 후 재시도 (5번 단계) |
| `cyclonedds` 빌드 실패 | `libssl-dev`, `bison`, `flex` 설치 후 재시도 |
| `scikit-sparse` 실패: `cholmod.h 없음` | `libsuitesparse-dev` 설치, 또는 `conda install -c conda-forge scikit-sparse` |
| `cv2.imencode` / OpenCV: `img is not a numpy array` (정상 배열인데도) | NumPy 2.x ↔ OpenCV 4.10 ABI 불일치. `pip install "numpy<2"` (7번 단계) |
| IK / 모션이 매우 느림 (풀이당 수십 ms) | 멀티스레드 BLAS 오버헤드. 스레드를 1로 고정 (10번 단계) |
| RealSense 인식 안 됨 | USB 3.0 포트 사용, `realsense-viewer`(또는 `pyrealsense2`)로 먼저 확인 |
| `rs-enumerate-devices: command not found` | `librealsense2-utils` 미설치. Python `pyrealsense2` 로 확인 |
| `Permission denied` / sudo 가 계속 비밀번호 요구 (FSM) | sudoers 경로가 인터프리터와 불일치. NOPASSWD 규칙 경로 확인 (8번 단계) |
| `pickle.load` 시 `RuntimeError: class version St6vector...basic_string` | pinocchio 버전이 다른 환경에서 만든 모델 캐시. 캐시(예: `high/ctrl/g1_29_model_cache.pkl`)를 삭제/이름변경 후 재생성 |
| 좀비 프로세스 잔존 | `pkill -9 -f rs_stream.py` 등으로 정리 후 재시작 |

### 계정 / 경로 이관 (예: 사용자 계정 변경)

다른 계정에서 설정한 프로젝트를 옮겨 홈 디렉토리가 바뀐 경우(예: `/home/olduser` → `/home/newuser`), 남아있는 하드코딩 경로를 점검하세요.

```bash
# 이전 계정명이 남아있는 곳 찾기
grep -rn "/home/<olduser>" $HOME/project/g1-motion-control/
```

홈 디렉토리 변경 후 흔히 깨지는 것들:

1. **sudoers NOPASSWD 규칙** — 이전 경로를 가리켜 sudo 가 조용히 비밀번호를 요구하고 FSM/모터 스크립트가 실패합니다. `visudo` 로 새 경로로 수정 (8번 단계).
2. **pinocchio 모델 캐시(`*.pkl`)** — 이전 환경에서 만든 캐시는 pinocchio 버전이 바뀌었을 때 언피클에 실패할 수 있습니다(`class version ...` 오류). 삭제하면 재생성됩니다.
3. **주석 / 문서** — `INSTALL.md` 나 `start_*.sh` 의 `# 위치:` 헤더 주석은 동작에 영향 없지만, 혼동을 줄이려면 갱신하세요.

`$HOME`, `$SCRIPT_DIR`, `$(dirname "$0")` 를 쓰는 스크립트는 새 계정에 자동으로 맞춰지므로 수정할 필요가 없습니다.
