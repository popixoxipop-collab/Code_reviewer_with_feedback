import java.util.List;
import java.util.Scanner;

/**
 * 학생 3명의 점수를 입력받아 평균/최고점/등급을 계산하고 기록을 출력하는 프로그램의 진입점.
 */
public class Main {
    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);

        System.out.println("===== 학생 성적 관리 프로그램 =====");

        GradeInputHandler inputHandler = new GradeInputHandler(scanner);
        ScoreCalculator scoreCalculator = new ScoreCalculator();
        GradeRanker gradeRanker = new GradeRanker(scoreCalculator);
        InputHistory inputHistory = new InputHistory();

        List<Student> students = inputHandler.inputStudents(3);
        inputHistory.addAll(students);

        double average = scoreCalculator.calculateAverage(students);
        int max = scoreCalculator.calculateMax(students);

        System.out.println("\n===== 결과 =====");
        System.out.printf("평균 점수: %.2f%n", average);
        System.out.println("최고 점수: " + max);

        System.out.println("\n===== 학생별 등급 =====");
        for (Student student : students) {
            String grade = gradeRanker.determineGrade(student, students);
            System.out.println(student.getName() + " - " + student.getScore() + "점 - 등급: " + grade);
        }

        inputHistory.printHistory();

        System.out.println("\n프로그램을 종료합니다.");
        scanner.close();
    }
}
