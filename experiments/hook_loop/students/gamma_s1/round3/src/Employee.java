/**
 * 직원 한 명의 이름 / 근무 시간 / 시급을 담는 데이터 클래스.
 *
 * 설계 메모(fan-in): 이 클래스는 PayrollCalculator, PayrollReport, Main
 * 3곳에서 직접 참조한다(fan-in=3). TaxDeduction과 PayslipArchive는 계산이
 * 끝난 숫자 값만 매개변수로 받도록 분리해서 Employee 타입을 몰라도 되게
 * 했다 — Employee에 필드가 추가/변경돼도 그 두 클래스는 영향을 받지 않는다.
 *
 * 타입 선택: hoursWorked/hourlyRate는 double을 쓴다. 사람이 입력하는 값이라
 * 크기가 작아(수십~수만 단위) double의 유효자릿수 범위 안에서 오버플로우
 * 걱정은 없다. 다만 이진 부동소수점 특성상 미세한 반올림 오차가 생길 수
 * 있어, 오차가 절대 없어야 하는 실제 회계 시스템이라면 BigDecimal이 더
 * 적합하다 — 이번 과제는 단발성 계산이라 double로 충분하다고 판단했다.
 */
public class Employee {

    private final String name;
    private final double hoursWorked;
    private final double hourlyRate;

    public Employee(String name, double hoursWorked, double hourlyRate) {
        if (name == null || name.trim().isEmpty()) {
            throw new IllegalArgumentException("이름은 비어 있을 수 없습니다.");
        }
        if (hoursWorked < 0) {
            throw new IllegalArgumentException("근무 시간은 음수일 수 없습니다: " + hoursWorked);
        }
        if (hourlyRate < 0) {
            throw new IllegalArgumentException("시급은 음수일 수 없습니다: " + hourlyRate);
        }
        this.name = name;
        this.hoursWorked = hoursWorked;
        this.hourlyRate = hourlyRate;
    }

    public String getName() {
        return name;
    }

    public double getHoursWorked() {
        return hoursWorked;
    }

    public double getHourlyRate() {
        return hourlyRate;
    }

    @Override
    public String toString() {
        return "Employee{name='" + name + "', hoursWorked=" + hoursWorked
                + ", hourlyRate=" + hourlyRate + "}";
    }
}
