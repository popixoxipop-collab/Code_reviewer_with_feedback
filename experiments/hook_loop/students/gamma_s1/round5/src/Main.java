import java.util.List;
import java.util.Scanner;

/**
 * 프로그램 진입점.
 *
 * 각 클래스는 StudentProfile(DTO)과 필요한 협력 객체만 생성자로 주고받으며,
 * 서로의 내부 구현이 아니라 공개 API(getter, 계산 메서드)에만 의존하도록
 * 이 클래스에서 조립(wiring)한다. Scanner도 여기서 하나만 만들어
 * ProfileInputHandler에 전달하고, 프로그램이 끝날 때 여기서만 닫는다.
 */
public class Main {

    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);

        ProfileInputHandler inputHandler = new ProfileInputHandler(scanner);
        List<StudentProfile> profiles = inputHandler.collectProfiles();

        HeightAnalyzer heightAnalyzer = new HeightAnalyzer(profiles);

        ProfileReport report = new ProfileReport(profiles);
        report.printReport();

        HeightSummary heightSummary = new HeightSummary(profiles, heightAnalyzer);
        heightSummary.printSummary();

        scanner.close();
    }
}
