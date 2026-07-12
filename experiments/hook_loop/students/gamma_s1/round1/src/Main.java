import java.util.Scanner;

/**
 * 학생 3명의 시험 점수를 입력받아 평균과 최고점을 계산해 출력하는 프로그램의 진입점.
 */
public class Main {

    private static final int STUDENT_COUNT = 3;

    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);

        GradeInputHandler inputHandler = new GradeInputHandler(scanner);
        Student[] students = inputHandler.inputStudents(STUDENT_COUNT);

        ScoreCalculator calculator = new ScoreCalculator();
        double average = calculator.calculateAverage(students);
        Student topStudent = calculator.findTopStudent(students);

        printResult(students, average, topStudent);

        scanner.close();
    }

    private static void printResult(Student[] students, double average, Student topStudent) {
        System.out.println();
        System.out.println("========== 성적 처리 결과 ==========");
        for (Student s : students) {
            System.out.printf("%-10s : %6.2f 점%n", s.getName(), s.getScore());
        }
        System.out.println("-------------------------------------");
        System.out.printf("평균 점수 : %6.2f 점%n", average);
        System.out.printf("최고 점수 : %s (%.2f 점)%n", topStudent.getName(), topStudent.getScore());
        System.out.println("=====================================");
    }
}
