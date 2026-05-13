import {
  IsNumber,
  IsPositive,
  IsString,
  IsUUID,
} from 'class-validator';

export class CreateAlertDto {
  @IsString()
  @IsUUID()
  productId: string;

  // BUG-29: rejeita NaN e valores negativos
  @IsNumber({ allowNaN: false, allowInfinity: false })
  @IsPositive()
  targetPrice: number;
}
