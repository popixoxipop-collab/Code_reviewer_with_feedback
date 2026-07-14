/**
 * 센서 측정값 1건을 담는 데이터 모델 클래스.
 *
 * [공유 컴포넌트 안내]
 * 이 클래스는 ReadingInputHandler(생성), ReadingValidator(검증 대상 값 형식 참고),
 * AnomalyReport(읽기), ReadingLog(읽기), Main(오케스트레이션) 등 최소 3곳 이상에서
 * 쓰이는 공유 데이터 모델이다. 필드를 추가/삭제하거나 getter의 반환 타입을 바꾸면
 * 위 클래스들이 모두 영향을 받으므로, 필드를 바꿀 때는 사용하는 곳을 전부 같이 점검해야 한다.
 *
 * 필드를 private으로 감추고 getter만 공개하는 이유는 외부 클래스가 SensorReading의
 * 내부 표현(필드 순서, 저장 방식 등)에 직접 의존하지 않게 하기 위함이다.
 * 다만 getHumidity()의 반환 타입 자체(int)는 그대로 노출되므로, 나중에 습도 저장 방식을
 * int에서 double로 바꾸면 이 getter를 호출하는 모든 곳(현재 AnomalyReport, ReadingLog 등)의
 * 산술/비교 연산이 함께 영향을 받는다. 즉 완전한 캡슐화라기보다는 "표현 접근을 getter로만
 * 강제하는 수준"의 격리이고, 인터페이스나 별도 DTO 변환 계층까지는 시간 관계상 만들지 않았다.
 */
public class SensorReading {

    private String sensorId;

    // 온도는 double로 저장.
    // 실험실 센서가 소수점 단위(예: 23.5도)까지 보고하는 경우가 흔하고, 정수로 반올림해서
    // 저장하면 AnomalyReport의 임계값(15.0~30.0) 근처에서 판정 정확도가 떨어질 수 있음.
    // 트레이드오프: double(8byte)이 int/float 대비 메모리를 더 쓰지만, 측정값 개수가
    // 실험실 규모(수십~수백 건) 수준이라 메모리/성능에 미치는 영향은 무시 가능한 수준으로 판단.
    private double temperature;

    // 습도는 int로 저장 (요구사항: 습도는 0~100 사이 정수 범위).
    // 대부분의 저가형 습도 센서가 정수 %만 출력하므로 double로 저장해도 실질적인
    // 정확도 이득이 없고, int(4byte)라 비교 연산도 더 단순함.
    // 오버플로우 관점: 0~100 범위는 int 표현 범위(약 ±21억)에 비해 압도적으로 작아
    // 오버플로우 여지가 사실상 없음 — 오히려 위험한 지점은 저장이 아니라 "문자열 -> int
    // 형변환" 시점(ReadingValidator에서 처리, 거기 주석 참고).
    private int humidity;

    public SensorReading(String sensorId, double temperature, int humidity) {
        this.sensorId = sensorId;
        this.temperature = temperature;
        this.humidity = humidity;
    }

    public String getSensorId() {
        return sensorId;
    }

    public double getTemperature() {
        return temperature;
    }

    public int getHumidity() {
        return humidity;
    }

    @Override
    public String toString() {
        return "[" + sensorId + "] 온도=" + temperature + "C, 습도=" + humidity + "%";
    }
}
